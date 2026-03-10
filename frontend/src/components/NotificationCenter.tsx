'use client';

import { useEffect, useState, useRef } from 'react';
import { Bell, Settings, X, Trash2 } from 'lucide-react';
import { useNotifications } from '@/hooks/useApi';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale/ru';
import { getVerbName } from '@/lib/verbTranslations';
import Link from 'next/link';

interface NotificationCenterProps {
    variant?: 'default' | 'mobile';
    isOpen?: boolean;
    onToggle?: () => void;
}

export function NotificationCenter({ variant = 'default', isOpen: externalIsOpen, onToggle }: NotificationCenterProps) {
    const [internalIsOpen, setInternalIsOpen] = useState(false);
    const isControlled = externalIsOpen !== undefined;
    const isOpen = isControlled ? externalIsOpen : internalIsOpen;
    const dropdownRef = useRef<HTMLDivElement>(null);
    
    const { notifications: notificationsData, unreadCount, markAsRead, markAllAsRead, deleteNotification, loading } = useNotifications();
    
    const notifications = Array.isArray(notificationsData) ? notificationsData : [];

    const toggleOpen = () => {
        if (onToggle) {
            onToggle();
        } else {
            setInternalIsOpen((v) => !v);
        }
    };

    const close = () => {
        if (onToggle && isOpen) {
            onToggle();
        } else {
            setInternalIsOpen(false);
        }
    };

    // Закрытие при клике вне компонента
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                close();
            }
        }

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen]);

    const handleNotificationClick = async (notification: any) => {
        if (!notification.is_read) {
            await markAsRead(notification.id);
        }
        
        // Навигация если есть action_url
        if (notification.action_url) {
            window.location.href = notification.action_url;
        }
    };

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Кнопка уведомлений */}
            <button
                onClick={toggleOpen}
                className={
                    variant === 'mobile'
                        ? "relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full hover:bg-slate-100"
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

            {/* Dropdown — только для desktop */}
            {isOpen && variant === 'default' && (
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
                            <Link
                                href="/notifications/settings"
                                className="p-1 hover:bg-slate-100 rounded"
                                aria-label="Настройки"
                                title="Настройки уведомлений"
                            >
                                <Settings className="w-4 h-4 text-gray-500" />
                            </Link>
                            <button
                                onClick={() => close()}
                                className="p-1 hover:bg-slate-100 rounded"
                                aria-label="Закрыть"
                            >
                                <X className="w-4 h-4 text-gray-500" />
                            </button>
                        </div>
                    </div>



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
                                {notifications.slice(0, 20).map((notification) => {
                                    const isUnread = !notification.is_read;
                                    // v2 API: timestamp вместо created_at
                                    const timestamp = notification.timestamp || notification.created_at;
                                    // v2 API: verb + description вместо title + message
                                    const title = notification.title || getVerbName(notification.verb);
                                    const message = notification.description || notification.short_message || notification.message;
                                    
                                    return (
                                    <li
                                        key={notification.id}
                                        className={`group p-3 border-b border-slate-100 hover:bg-slate-100 transition-colors ${
                                            isUnread ? 'bg-sky-50/50' : ''
                                        }`}
                                    >
                                        <div className="flex items-start gap-2.5">
                                            {isUnread && (
                                                <div className="w-1.5 h-1.5 bg-sky-600 rounded-full mt-1.5 flex-shrink-0" />
                                            )}
                                            <div 
                                                onClick={() => handleNotificationClick(notification)}
                                                className="flex-1 min-w-0 cursor-pointer"
                                            >
                                                <h4 className="font-medium text-sm mb-0.5 truncate text-gray-800">
                                                    {title}
                                                </h4>
                                                <p className="text-xs text-gray-600 line-clamp-2 mb-1">
                                                    {message}
                                                </p>
                                                <p className="text-[10px] text-gray-400">
                                                    {formatDistanceToNow(new Date(timestamp), {
                                                        addSuffix: true,
                                                        locale: ru,
                                                    })}
                                                </p>
                                            </div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    deleteNotification(notification.id);
                                                }}
                                                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-50 rounded transition-all flex-shrink-0"
                                                aria-label="Удалить"
                                                title="Удалить уведомление"
                                            >
                                                <Trash2 className="w-3.5 h-3.5 text-gray-400 hover:text-red-600" />
                                            </button>
                                        </div>
                                    </li>
                                )})}
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

/** Встраиваемая панель уведомлений (для выдвижных блоков) */
export function NotificationPanel({ onClose }: { onClose?: () => void }) {
    const { notifications: notificationsData, unreadCount, markAsRead, markAllAsRead, deleteNotification, loading } = useNotifications();
    const notifications = Array.isArray(notificationsData) ? notificationsData : [];

    const handleNotificationClick = async (notification: any) => {
        if (!notification.is_read) {
            await markAsRead(notification.id);
        }
        if (notification.action_url) {
            window.location.href = notification.action_url;
        }
    };

    return (
        <div className="flex flex-col max-h-[60vh] bg-white rounded-xl shadow-sm ring-1 ring-gray-100 overflow-hidden">
            <div className="flex items-center justify-between p-3 border-b border-slate-100">
                <h3 className="font-semibold text-sm">Уведомления</h3>
                <div className="flex items-center gap-2">
                    {unreadCount > 0 && (
                        <button onClick={markAllAsRead} className="text-xs text-sky-600 hover:text-sky-700 font-medium">
                            Прочитать все
                        </button>
                    )}
                    <Link
                        href="/notifications/settings"
                        className="p-1 hover:bg-slate-100 rounded"
                        aria-label="Настройки"
                        title="Настройки уведомлений"
                    >
                        <Settings className="w-4 h-4 text-gray-500" />
                    </Link>
                    {onClose && (
                        <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded" aria-label="Закрыть">
                            <X className="w-4 h-4 text-gray-500" />
                        </button>
                    )}
                </div>
            </div>



            <div className="overflow-y-auto flex-1">
                {loading ? (
                    <div className="p-6 text-center text-gray-500 text-sm">Загрузка...</div>
                ) : notifications.length === 0 ? (
                    <div className="p-6 text-center text-gray-500">
                        <Bell className="w-10 h-10 mx-auto mb-2 opacity-20 text-gray-400" />
                        <p className="text-sm">Нет уведомлений</p>
                    </div>
                ) : (
                    <ul>
                        {notifications.slice(0, 20).map((notification) => {
                            const isUnread = !notification.is_read;
                            // v2 API: timestamp вместо created_at
                            const timestamp = notification.timestamp || notification.created_at;
                            // v2 API: verb + description вместо title + message
                            const title = notification.title || getVerbName(notification.verb);
                            const message = notification.description || notification.short_message || notification.message;
                            
                            return (
                            <li
                                key={notification.id}
                                onClick={() => handleNotificationClick(notification)}
                                className={`p-3 border-b border-slate-100 hover:bg-slate-100 cursor-pointer transition-colors ${
                                    isUnread ? 'bg-sky-50/50' : ''
                                }`}
                            >
                                <div className="flex items-start gap-2">
                                    {isUnread && (
                                        <div className="w-1.5 h-1.5 bg-sky-600 rounded-full mt-1.5 flex-shrink-0" />
                                    )}
                                    <div className="flex-1 min-w-0">
                                        <h4 className="font-medium text-sm mb-0.5 truncate text-gray-800">{title}</h4>
                                        <p className="text-xs text-gray-600 line-clamp-2 mb-1">{message}</p>
                                        <p className="text-[10px] text-gray-400">
                                            {formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ru })}
                                        </p>
                                    </div>
                                </div>
                            </li>
                        )})}
                    </ul>
                )}
            </div>

            {notifications.length > 0 && (
                <div className="p-2 border-t border-slate-100 bg-slate-50 text-center">
                    <a href="/notifications" className="text-xs text-sky-600 hover:text-sky-700 font-medium">Показать все</a>
                </div>
            )}
        </div>
    );
}
