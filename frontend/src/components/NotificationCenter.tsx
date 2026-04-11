'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import { Bell, Settings, X, Trash2 } from 'lucide-react';
import { useNotifications } from '@/hooks/useApi';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale/ru';
import { getVerbName } from '@/lib/verbTranslations';
import Link from 'next/link';
import type { NotificationItem } from '@/contexts/NotificationsContext';

interface NotificationCenterProps {
    variant?: 'default' | 'mobile';
    isOpen?: boolean;
    onToggle?: () => void;
}

function getNotificationTitle(notification: NotificationItem): string {
    return notification.title || getVerbName(notification.verb || '');
}

function getNotificationMessage(notification: NotificationItem): string {
    return notification.description || notification.short_message || notification.message || '';
}

function getNotificationTimestamp(notification: NotificationItem): string | null {
    return notification.timestamp || notification.created_at || null;
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

    const close = useCallback(() => {
        if (onToggle && isOpen) {
            onToggle();
        } else {
            setInternalIsOpen(false);
        }
    }, [isOpen, onToggle]);

    // Закрытие при клике вне компонента (только для desktop варианта)
    useEffect(() => {
        // Для mobile варианта не используем этот обработчик, 
        // т.к. панель уведомлений рендерится отдельно в AppShell
        if (!isOpen || variant === 'mobile') return;

        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                close();
            }
        }

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [close, isOpen, variant]);

    const handleNotificationClick = async (notification: NotificationItem) => {
        if (!notification.is_read) {
            await markAsRead(notification.id);
        }
        
        // Навигация если есть action_url
        if (notification.action_url) {
            window.location.assign(notification.action_url);
        }
    };

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Кнопка уведомлений */}
            <button
                onClick={toggleOpen}
                className={
                    variant === 'mobile'
                        ? "app-icon-button relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                        : "app-icon-button relative flex h-10 w-10 items-center justify-center rounded-full"
                }
                aria-label="Уведомления"
            >
                <Bell size={18} />
                {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center font-bold">
                        {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                )}
            </button>

            {/* Dropdown — только для desktop */}
            {isOpen && variant === 'default' && (
                <div className="app-menu absolute right-0 top-12 z-[60] flex max-h-[600px] w-80 flex-col rounded-xl sm:w-96 animate-fade-in">
                    {/* Заголовок */}
                    <div className="app-divider flex items-center justify-between border-b p-4">
                        <h3 className="text-base font-semibold text-[var(--foreground)]">Уведомления</h3>
                        <div className="flex items-center gap-2">
                            {unreadCount > 0 && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        markAllAsRead();
                                    }}
                                    className="app-link-accent text-xs font-medium"
                                >
                                    Прочитать все
                                </button>
                            )}
                            <Link
                                href="/notifications/settings"
                                onClick={(e) => e.stopPropagation()}
                                className="app-icon-button rounded p-1"
                                aria-label="Настройки"
                                title="Настройки уведомлений"
                            >
                                <Settings className="h-4 w-4" />
                            </Link>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    close();
                                }}
                                className="app-icon-button rounded p-1"
                                aria-label="Закрыть"
                            >
                                <X className="h-4 w-4" />
                            </button>
                        </div>
                    </div>



                    {/* Список уведомлений */}
                    <div className="overflow-y-auto flex-1">
                        {loading ? (
                            <div className="app-text-muted p-8 text-center text-sm">
                                Загрузка...
                            </div>
                        ) : notifications.length === 0 ? (
                            <div className="app-text-muted p-8 text-center">
                                <Bell className="mx-auto mb-2 h-12 w-12 opacity-20" />
                                <p className="text-sm">Нет уведомлений</p>
                            </div>
                        ) : (
                            <ul>
                                {notifications.slice(0, 20).map((notification) => {
                                    const isUnread = !notification.is_read;
                                    const timestamp = getNotificationTimestamp(notification);
                                    const title = getNotificationTitle(notification);
                                    const message = getNotificationMessage(notification);
                                    
                                    return (
                                    <li
                                        key={notification.id}
                                        className={`app-divider group border-b p-3 transition-colors hover:bg-[var(--surface-secondary)] ${
                                            isUnread ? 'app-unread-surface' : ''
                                        }`}
                                    >
                                        <div className="flex items-start gap-2.5">
                                            {isUnread && (
                                                <div className="app-dot-accent mt-1.5 h-1.5 w-1.5 rounded-full flex-shrink-0" />
                                            )}
                                            <div 
                                                onClick={() => handleNotificationClick(notification)}
                                                className="flex-1 min-w-0 cursor-pointer"
                                            >
                                                <h4 className="mb-0.5 truncate text-sm font-medium text-[var(--foreground)]">
                                                    {title}
                                                </h4>
                                                <p className="app-text-muted mb-1 line-clamp-2 text-xs">
                                                    {message}
                                                </p>
                                                <p className="app-text-muted text-[10px]">
                                                    {timestamp ? formatDistanceToNow(new Date(timestamp), {
                                                        addSuffix: true,
                                                        locale: ru,
                                                    }) : 'Только что'}
                                                </p>
                                            </div>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    deleteNotification(notification.id);
                                                }}
                                                className="flex-shrink-0 rounded p-1.5 opacity-0 transition-all group-hover:opacity-100 hover:bg-[var(--danger-soft)]"
                                                aria-label="Удалить"
                                                title="Удалить уведомление"
                                            >
                                                <Trash2 className="h-3.5 w-3.5 text-[var(--muted-foreground)] hover:text-red-500" />
                                            </button>
                                        </div>
                                    </li>
                                )})}
                            </ul>
                        )}
                    </div>

                    {/* Футер */}
                    <div className="app-divider app-surface-muted border-t p-3 text-center">
                        <a
                            href="/notifications"
                            onClick={(e) => e.stopPropagation()}
                            className="app-link-accent text-xs font-medium"
                        >
                            Показать все уведомления
                        </a>
                    </div>
                </div>
            )}
        </div>
    );
}

/** Встраиваемая панель уведомлений (для выдвижных блоков) */
export function NotificationPanel({ onClose }: { onClose?: () => void }) {
    const { notifications: notificationsData, unreadCount, markAsRead, markAllAsRead, loading } = useNotifications();
    const notifications = Array.isArray(notificationsData) ? notificationsData : [];

    const handleNotificationClick = async (notification: NotificationItem) => {
        if (!notification.is_read) {
            await markAsRead(notification.id);
        }
        if (notification.action_url) {
            window.location.assign(notification.action_url);
        }
    };

    return (
        <div className="app-menu flex max-h-[60vh] flex-col overflow-hidden rounded-xl">
            <div className="app-divider flex items-center justify-between border-b p-3">
                <h3 className="text-sm font-semibold text-[var(--foreground)]">Уведомления</h3>
                <div className="flex items-center gap-2">
                    {unreadCount > 0 && (
                        <button 
                            onClick={(e) => {
                                e.stopPropagation();
                                markAllAsRead();
                            }} 
                            className="app-link-accent text-xs font-medium"
                        >
                            Прочитать все
                        </button>
                    )}
                    <Link
                        href="/notifications/settings"
                        onClick={(e) => e.stopPropagation()}
                        className="app-icon-button rounded p-1"
                        aria-label="Настройки"
                        title="Настройки уведомлений"
                    >
                        <Settings className="h-4 w-4" />
                    </Link>
                    {onClose && (
                        <button onClick={onClose} className="app-icon-button rounded p-1" aria-label="Закрыть">
                            <X className="h-4 w-4" />
                        </button>
                    )}
                </div>
            </div>



            <div className="overflow-y-auto flex-1">
                {loading ? (
                    <div className="app-text-muted p-8 text-center text-sm">Загрузка...</div>
                ) : notifications.length === 0 ? (
                    <div className="app-text-muted p-8 text-center">
                        <Bell className="mx-auto mb-2 h-12 w-12 opacity-20" />
                        <p className="text-sm">Нет уведомлений</p>
                    </div>
                ) : (
                    <ul>
                        {notifications.slice(0, 20).map((notification) => {
                            const isUnread = !notification.is_read;
                            const timestamp = getNotificationTimestamp(notification);
                            const title = getNotificationTitle(notification);
                            const message = getNotificationMessage(notification);
                            
                            return (
                            <li
                                key={notification.id}
                                onClick={() => handleNotificationClick(notification)}
                                className={`app-divider cursor-pointer border-b p-3 transition-colors hover:bg-[var(--surface-secondary)] ${
                                    isUnread ? 'app-unread-surface' : ''
                                }`}
                            >
                                <div className="flex items-start gap-2">
                                    {isUnread && (
                                        <div className="app-dot-accent mt-1.5 h-1.5 w-1.5 rounded-full flex-shrink-0" />
                                    )}
                                    <div className="flex-1 min-w-0">
                                        <h4 className="mb-0.5 truncate text-sm font-medium text-[var(--foreground)]">{title}</h4>
                                        <p className="app-text-muted mb-1 line-clamp-2 text-xs">{message}</p>
                                        <p className="app-text-muted text-[10px]">
                                            {timestamp ? formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ru }) : 'Только что'}
                                        </p>
                                    </div>
                                </div>
                            </li>
                        )})}
                    </ul>
                )}
            </div>

            <div className="app-divider app-surface-muted border-t p-2 text-center">
                <a 
                    href="/notifications" 
                    onClick={(e) => e.stopPropagation()}
                    className="app-link-accent text-xs font-medium"
                >
                    Показать все
                </a>
            </div>
        </div>
    );
}
