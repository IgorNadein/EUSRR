"use client";

import { useState, useEffect } from "react";
import { Bell, BellOff, Eye, EyeOff, Loader2 } from "lucide-react";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";

interface Calendar {
  id: number;
  name: string;
  title?: string;
  color?: string;
  is_subscribed?: boolean;
  subscriber_count?: number;
  visibility?: string;
  owner_user?: { id: number; username: string; full_name: string } | null;
  owner_department?: { id: number; name: string } | null;
}

interface Subscription {
  id: number;
  calendar: number;
  calendar_title: string;
  calendar_color: string;
  is_visible: boolean;
  color_override: string | null;
  notify_on_new_event: boolean;
  notify_on_event_change: boolean;
  can_edit: boolean;
  can_manage: boolean;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onUpdate?: () => void;
}

export function CalendarSubscriptionsModal({ isOpen, onClose, onUpdate }: Props) {
  const [availableCalendars, setAvailableCalendars] = useState<Calendar[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"available" | "subscribed">("available");

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [calendarsData, subsData] = await Promise.all([
        apiClient.getCalendars(),
        apiClient.getCalendarSubscriptions(),
      ]);

      const calendarsList = Array.isArray(calendarsData) 
        ? calendarsData 
        : calendarsData?.results || [];
      
      const subsList = Array.isArray(subsData) 
        ? subsData 
        : subsData?.results || [];

      setAvailableCalendars(calendarsList);
      setSubscriptions(subsList);
    } catch (err) {
      console.error("Ошибка загрузки данных:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (calendarId: number) => {
    try {
      await apiClient.subscribeToCalendar(calendarId);
      await loadData();
      onUpdate?.();
    } catch (err) {
      console.error("Ошибка подписки:", err);
      alert("Не удалось подписаться на календарь");
    }
  };

  const handleUnsubscribe = async (calendarId: number) => {
    if (!confirm("Отписаться от календаря?")) return;
    
    try {
      await apiClient.unsubscribeFromCalendar(calendarId);
      await loadData();
      onUpdate?.();
    } catch (err) {
      console.error("Ошибка отписки:", err);
      alert("Не удалось отписаться от календаря");
    }
  };

  const toggleVisibility = async (sub: Subscription) => {
    try {
      await apiClient.updateSubscription(sub.id, {
        is_visible: !sub.is_visible,
      });
      await loadData();
      onUpdate?.();
    } catch (err) {
      console.error("Ошибка обновления:", err);
    }
  };

  const toggleNotifications = async (sub: Subscription) => {
    try {
      await apiClient.updateSubscription(sub.id, {
        notify_on_new_event: !sub.notify_on_new_event,
        notify_on_event_change: !sub.notify_on_event_change,
      });
      await loadData();
    } catch (err) {
      console.error("Ошибка обновления:", err);
    }
  };

  const getCalendarOwner = (calendar: Calendar) => {
    if (calendar.owner_user) {
      return calendar.owner_user.full_name || calendar.owner_user.username;
    }
    if (calendar.owner_department) {
      return calendar.owner_department.name;
    }
    return "Общий";
  };

  const subscribedCalendarIds = new Set(subscriptions.map(s => s.calendar));
  const unsubscribedCalendars = availableCalendars.filter(
    cal => !subscribedCalendarIds.has(cal.id)
  );

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md" noPadding noHeader>
      <div className="overflow-y-auto">
        {/* Header */}
        <div className="app-divider flex items-center justify-between border-b px-4 py-3 sm:px-6 sm:py-4">
          <h3 className="text-base font-semibold text-[var(--foreground)] sm:text-lg">Подписки на календари</h3>
        </div>

        {/* Tabs */}
        <div className="app-divider flex border-b">
          <button
            onClick={() => setActiveTab("available")}
            className={`flex-1 px-3 sm:px-6 py-2.5 sm:py-3 text-xs sm:text-sm font-medium transition ${
              activeTab === "available"
                ? "border-b-2 border-[var(--accent-primary)] text-[var(--accent-primary-strong)]"
                : "app-text-muted hover:text-[var(--foreground)]"
            }`}
          >
            Доступные ({unsubscribedCalendars.length})
          </button>
          <button
            onClick={() => setActiveTab("subscribed")}
            className={`flex-1 px-3 sm:px-6 py-2.5 sm:py-3 text-xs sm:text-sm font-medium transition ${
              activeTab === "subscribed"
                ? "border-b-2 border-[var(--accent-primary)] text-[var(--accent-primary-strong)]"
                : "app-text-muted hover:text-[var(--foreground)]"
            }`}
          >
            Подписки ({subscriptions.length})
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[500px] overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={24} className="app-text-muted animate-spin" />
            </div>
          ) : activeTab === "available" ? (
            <div className="space-y-2">
              {unsubscribedCalendars.length === 0 ? (
                <p className="app-text-muted py-8 text-center text-sm">
                  Нет доступных календарей для подписки
                </p>
              ) : (
                unsubscribedCalendars.map((cal) => (
                  <div
                    key={cal.id}
                    className="app-surface flex items-center justify-between rounded-lg p-4 transition hover:bg-[var(--surface-secondary)]"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="h-4 w-4 rounded"
                        style={{ backgroundColor: cal.color || "var(--accent-primary)" }}
                      />
                      <div>
                        <p className="font-medium text-[var(--foreground)]">{cal.name || cal.title}</p>
                        <p className="app-text-muted text-xs">{getCalendarOwner(cal)}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleSubscribe(cal.id)}
                      className="app-action-primary rounded-lg px-4 py-2 text-sm font-medium"
                    >
                      Подписаться
                    </button>
                  </div>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {subscriptions.length === 0 ? (
                <p className="app-text-muted py-8 text-center text-sm">
                  У вас нет подписок на календари
                </p>
              ) : (
                subscriptions.map((sub) => (
                  <div
                    key={sub.id}
                    className="app-surface rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="h-4 w-4 rounded"
                          style={{ backgroundColor: sub.color_override || sub.calendar_color }}
                        />
                        <div>
                          <p className="font-medium text-[var(--foreground)]">{sub.calendar_title}</p>
                          <div className="mt-1 flex gap-2">
                            {sub.can_edit && (
                              <span className="app-feedback-success rounded px-2 py-0.5 text-xs">
                                Редактирование
                              </span>
                            )}
                            {sub.can_manage && (
                              <span className="rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                                Управление
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-1">
                        <button
                          onClick={() => toggleVisibility(sub)}
                          className="app-action-secondary rounded-lg p-2 transition"
                          title={sub.is_visible ? "Скрыть" : "Показать"}
                        >
                          {sub.is_visible ? (
                            <Eye size={16} className="app-text-muted" />
                          ) : (
                            <EyeOff size={16} className="app-text-muted" />
                          )}
                        </button>
                        <button
                          onClick={() => toggleNotifications(sub)}
                          className="app-action-secondary rounded-lg p-2 transition"
                          title={sub.notify_on_new_event ? "Отключить уведомления" : "Включить уведомления"}
                        >
                          {sub.notify_on_new_event ? (
                            <Bell size={16} className="app-text-muted" />
                          ) : (
                            <BellOff size={16} className="app-text-muted" />
                          )}
                        </button>
                        <button
                          onClick={() => handleUnsubscribe(sub.calendar)}
                          className="app-action-danger rounded-lg px-3 py-2 text-sm transition"
                        >
                          Отписаться
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="app-divider flex justify-end border-t px-6 py-4">
          <button
            onClick={onClose}
            className="app-action-secondary rounded-lg px-4 py-2 text-sm font-medium"
          >
            Закрыть
          </button>
        </div>
      </div>
    </Modal>
  );
}
