'use client';

import { useEffect, useState, useRef } from 'react';
import { Bell, Settings, X } from 'lucide-react';
import { useNotifications } from '@/hooks/useApi';
import { useWebPush } from '@/hooks/useWebPush';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale/ru';

export function NotificationCenter() {
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
                className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
                aria-label="Уведомления"
            >
                <Bell className="w-6 h-6" />
                {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
                        {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                )}
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-xl border border-gray-200 z-50 max-h-[600px] flex flex-col">
                    {/* Заголовок */}
                    <div className="flex items-center justify-between p-4 border-b">
                        <h3 className="font-semibold text-lg">Уведомления</h3>
                        <div className="flex items-center gap-2">
                            {unreadCount > 0 && (
                                <button
                                    onClick={markAllAsRead}
                                    className="text-sm text-blue-600 hover:text-blue-700"
                                >
                                    Прочитать все
                                </button>
                            )}
                            <button
                                onClick={() => setShowSettings(!showSettings)}
                                className="p-1 hover:bg-gray-100 rounded"
                                aria-label="Настройки"
                            >
                                <Settings className="w-5 h-5" />
                            </button>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="p-1 hover:bg-gray-100 rounded"
                                aria-label="Закрыть"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                    </div>

                    {/* Настройки Push */}
                    {showSettings && (
                        <div className="p-4 bg-gray-50 border-b">
                            <h4 className="font-medium mb-2">Push уведомления</h4>
                            {!isSupported ? (
                                <p className="text-sm text-gray-500">
                                    Push уведомления не поддерживаются вашим браузером
                                </p>
                            ) : permission === 'denied' ? (
                                <p className="text-sm text-red-500">
                                    Вы запретили уведомления. Измените настройки браузера.
                                </p>
                            ) : (
                                <div className="flex items-center justify-between">
                                    <span className="text-sm">
                                        {isSubscribed ? 'Включены' : 'Отключены'}
                                    </span>
                                    <button
                                        onClick={handleTogglePush}
                                        disabled={pushLoading}
                                        className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                                            isSubscribed
                                                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                                : 'bg-blue-600 text-white hover:bg-blue-700'
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
                            <div className="p-8 text-center text-gray-500">
                                Загрузка...
                            </div>
                        ) : notifications.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">
                                <Bell className="w-12 h-12 mx-auto mb-2 opacity-30" />
                                <p>Нет уведомлений</p>
                            </div>
                        ) : (
                            <ul>
                                {notifications.slice(0, 20).map((notification) => (
                                    <li
                                        key={notification.id}
                                        onClick={() => handleNotificationClick(notification)}
                                        className={`p-4 border-b hover:bg-gray-50 cursor-pointer transition-colors ${
                                            !notification.is_read ? 'bg-blue-50' : ''
                                        }`}
                                    >
                                        <div className="flex items-start gap-3">
                                            {!notification.is_read && (
                                                <div className="w-2 h-2 bg-blue-600 rounded-full mt-2 flex-shrink-0" />
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <h4 className="font-medium text-sm mb-1 truncate">
                                                    {notification.title}
                                                </h4>
                                                <p className="text-sm text-gray-600 line-clamp-2 mb-1">
                                                    {notification.short_message || notification.message}
                                                </p>
                                                <p className="text-xs text-gray-400">
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
                        <div className="p-3 border-t bg-gray-50 text-center">
                            <a
                                href="/notifications"
                                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
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
