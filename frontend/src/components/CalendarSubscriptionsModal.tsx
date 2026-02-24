"use client";

import { useState, useEffect } from "react";
import { X, Check, Bell, BellOff, Eye, EyeOff, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";

interface Calendar {
  id: number;
  name: string;
  title?: string;
  color: string;
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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 transition-all duration-200">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl transition-all duration-300 ease-out">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <h3 className="text-lg font-semibold text-gray-900">Подписки на календари</h3>
          <button
            onClick={onClose}
            className="rounded-full p-1 hover:bg-gray-100"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100">
          <button
            onClick={() => setActiveTab("available")}
            className={`flex-1 px-6 py-3 text-sm font-medium transition ${
              activeTab === "available"
                ? "border-b-2 border-sky-500 text-sky-600"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Доступные ({unsubscribedCalendars.length})
          </button>
          <button
            onClick={() => setActiveTab("subscribed")}
            className={`flex-1 px-6 py-3 text-sm font-medium transition ${
              activeTab === "subscribed"
                ? "border-b-2 border-sky-500 text-sky-600"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Подписки ({subscriptions.length})
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[500px] overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={24} className="animate-spin text-gray-400" />
            </div>
          ) : activeTab === "available" ? (
            <div className="space-y-2">
              {unsubscribedCalendars.length === 0 ? (
                <p className="py-8 text-center text-sm text-gray-500">
                  Нет доступных календарей для подписки
                </p>
              ) : (
                unsubscribedCalendars.map((cal) => (
                  <div
                    key={cal.id}
                    className="flex items-center justify-between rounded-lg border border-gray-200 p-4 transition hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="h-4 w-4 rounded"
                        style={{ backgroundColor: cal.color }}
                      />
                      <div>
                        <p className="font-medium text-gray-900">{cal.name || cal.title}</p>
                        <p className="text-xs text-gray-500">{getCalendarOwner(cal)}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleSubscribe(cal.id)}
                      className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-600"
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
                <p className="py-8 text-center text-sm text-gray-500">
                  У вас нет подписок на календари
                </p>
              ) : (
                subscriptions.map((sub) => (
                  <div
                    key={sub.id}
                    className="rounded-lg border border-gray-200 p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className="h-4 w-4 rounded"
                          style={{ backgroundColor: sub.color_override || sub.calendar_color }}
                        />
                        <div>
                          <p className="font-medium text-gray-900">{sub.calendar_title}</p>
                          <div className="mt-1 flex gap-2">
                            {sub.can_edit && (
                              <span className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-700">
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
                          className="rounded-lg border border-gray-300 p-2 transition hover:bg-gray-50"
                          title={sub.is_visible ? "Скрыть" : "Показать"}
                        >
                          {sub.is_visible ? (
                            <Eye size={16} className="text-gray-600" />
                          ) : (
                            <EyeOff size={16} className="text-gray-400" />
                          )}
                        </button>
                        <button
                          onClick={() => toggleNotifications(sub)}
                          className="rounded-lg border border-gray-300 p-2 transition hover:bg-gray-50"
                          title={sub.notify_on_new_event ? "Отключить уведомления" : "Включить уведомления"}
                        >
                          {sub.notify_on_new_event ? (
                            <Bell size={16} className="text-gray-600" />
                          ) : (
                            <BellOff size={16} className="text-gray-400" />
                          )}
                        </button>
                        <button
                          onClick={() => handleUnsubscribe(sub.calendar)}
                          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 transition hover:bg-red-100"
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
        <div className="flex justify-end border-t border-gray-100 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
