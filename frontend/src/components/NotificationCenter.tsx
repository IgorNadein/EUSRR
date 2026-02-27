'use client';

import { useEffect, useState, useRef } from 'react';
import { Bell, Settings, X } from 'lucide-react';
import { useNotifications } from '@/hooks/useApi';
import { useWebPush } from '@/hooks/useWebPush';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale/ru';

interface NotificationCenterProps {
    variant?: 'default' | 'mobile';
}

export function NotificationCenter({ variant = 'default' }: NotificationCenterProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    
    const { notifications: notificationsData, unreadCount, markAsRead, markAllAsRead, loading } = useNotifications();
    const { isSupported, isSubscribed, subscribe, unsubscribe, permission, isLoading: pushLoading } = useWebPush();
    
    // Обеспечиваем что notifications всегда массив
    const notifications = Array.isArray(notificationsData) ? notificationsData : [];

    // Закрытие при клике вне компонента
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
                setShowSettings(false);
            }
        }

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleNotificationClick = async (notification: any) => {
        if (!notification.is_read) {
            await markAsRead(notification.id);
        }
        
        // Навигация если есть action_url
        if (notification.action_url) {
            window.location.href = notification.action_url;
        }
    };

    const handleTogglePush = async () => {
        if (isSubscribed) {
            await unsubscribe();
        } else {
            await subscribe();
        }
    };

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Кнопка уведомлений */}
            <button
                onClick={() => {
                    setIsOpen(!isOpen);
                    setShowSettings(false);
                }}
                className={
                    variant === 'mobile'
                        ? "relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-gray-200 bg-gray-50 hover:bg-slate-100"
                        : "relative flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
                }
                aria-label="Уведомления"
            >
                <Bell size={18} className="text-gray-600" />
                {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center font-bold">
                        {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                )}
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute right-0 top-12 z-[60] w-80 sm:w-96 bg-white rounded-xl shadow-lg ring-1 ring-slate-100 max-h-[600px] flex flex-col animate-fade-in">
                    {/* Заголовок */}
                    <div className="flex items-center justify-between p-4 border-b border-slate-100">
                        <h3 className="font-semibold text-base">Уведомления</h3>
                        <div className="flex items-center gap-2">
                            {unreadCount > 0 && (
                                <button
                                    onClick={markAllAsRead}
                                    className="text-xs text-sky-600 hover:text-sky-700 font-medium"
                                >
                                    Прочитать все
                                </button>
                            )}
                            <button
                                onClick={() => setShowSettings(!showSettings)}
                                className="p-1 hover:bg-slate-100 rounded"
                                aria-label="Настройки"
                            >
                                <Settings className="w-4 h-4 text-gray-500" />
                            </button>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="p-1 hover:bg-slate-100 rounded"
                                aria-label="Закрыть"
                            >
                                <X className="w-4 h-4 text-gray-500" />
                            </button>
                        </div>
                    </div>

                    {/* Настройки Push */}
                    {showSettings && (
                        <div className="p-4 bg-slate-50 border-b border-slate-100">
                            <h4 className="font-medium mb-2 text-sm">Push уведомления</h4>
                            {!isSupported ? (
                                <p className="text-xs text-gray-500">
                                    Push уведомления не поддерживаются вашим браузером
                                </p>
                            ) : permission === 'denied' ? (
                                <p className="text-xs text-red-500">
                                    Вы запретили уведомления. Измените настройки браузера.
                                </p>
                            ) : (
                                <div className="flex items-center justify-between">
                                    <span className="text-xs text-gray-600">
                                        {isSubscribed ? 'Включены' : 'Отключены'}
                                    </span>
                                    <button
                                        onClick={handleTogglePush}
                                        disabled={pushLoading}
                                        className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                                            isSubscribed
                                                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                                : 'bg-sky-600 text-white hover:bg-sky-700'
                                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                                    >
                                        {pushLoading ? 'Загрузка...' : isSubscribed ? 'Отключить' : 'Включить'}
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Список уведомлений */}
                    <div className="overflow-y-auto flex-1">
                        {loading ? (
                            <div className="p-8 text-center text-gray-500 text-sm">
                                Загрузка...
                            </div>
                        ) : notifications.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">
                                <Bell className="w-12 h-12 mx-auto mb-2 opacity-20 text-gray-400" />
                                <p className="text-sm">Нет уведомлений</p>
                            </div>
                        ) : (
                            <ul>
                                {notifications.slice(0, 20).map((notification) => (
                                    <li
                                        key={notification.id}
                                        onClick={() => handleNotificationClick(notification)}
                                        className={`p-3 border-b border-slate-100 hover:bg-slate-100 cursor-pointer transition-colors ${
                                            !notification.is_read ? 'bg-sky-50/50' : ''
                                        }`}
                                    >
                                        <div className="flex items-start gap-2.5">
                                            {!notification.is_read && (
                                                <div className="w-1.5 h-1.5 bg-sky-600 rounded-full mt-1.5 flex-shrink-0" />
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <h4 className="font-medium text-sm mb-0.5 truncate text-gray-800">
                                                    {notification.title}
                                                </h4>
                                                <p className="text-xs text-gray-600 line-clamp-2 mb-1">
                                                    {notification.short_message || notification.message}
                                                </p>
                                                <p className="text-[10px] text-gray-400">
                                                    {formatDistanceToNow(new Date(notification.created_at), {
                                                        addSuffix: true,
                                                        locale: ru,
                                                    })}
                                                </p>
                                            </div>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>

                    {/* Футер */}
                    {notifications.length > 0 && (
                        <div className="p-3 border-t border-slate-100 bg-slate-50 text-center">
                            <a
                                href="/notifications"
                                className="text-xs text-sky-600 hover:text-sky-700 font-medium"
                            >
                                Показать все уведомления
                            </a>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
