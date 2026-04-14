'use client';

import { AppShell } from '@/components/AppShell';
import { apiClient } from '@/lib/api';
import { Bell, CheckCheck, Filter, Search, Trash2 } from 'lucide-react';
import { useState, useMemo, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale/ru';
import { getVerbCategory, getVerbName } from '@/lib/verbTranslations';
import { resolveNotificationActionUrl } from '@/lib/notifications/actionUrl';

export default function NotificationsPage() {
  // Локальное состояние для ВСЕХ уведомлений (не только непрочитанных)
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [filterRead, setFilterRead] = useState<'all' | 'unread' | 'read'>('all');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Загрузка всех уведомлений (100 последних)
  useEffect(() => {
    async function fetchAllNotifications() {
      try {
        const data = await apiClient.getNotifications({ page_size: 100 });
        const notifs = data.notifications || data.results || data;
        setNotifications(Array.isArray(notifs) ? notifs : []);
      } catch (err) {
        console.error('Ошибка загрузки уведомлений:', err);
      } finally {
        setLoading(false);
      }
    }

    fetchAllNotifications();
  }, []);

  // Функции для операций с уведомлениями
  const markAsRead = async (id: number) => {
    try {
      await apiClient.markNotificationAsRead(id);
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (err) {
      console.error('Ошибка отметки уведомления:', err);
    }
  };

  const markAllAsRead = async () => {
    try {
      await apiClient.markAllNotificationsAsRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Ошибка отметки всех уведомлений:', err);
    }
  };

  const deleteNotification = async (id: number) => {
    try {
      await apiClient.deleteNotification(id);
      setNotifications(prev => prev.filter(n => n.id !== id));
    } catch (err) {
      console.error('Ошибка удаления уведомления:', err);
    }
  };

  const deleteAllRead = async (): Promise<number> => {
    try {
      const readNotifications = notifications.filter(n => n.is_read);
      const count = readNotifications.length;
      await apiClient.deleteAllReadNotifications();
      setNotifications(prev => prev.filter(n => !n.is_read));
      return count;
    } catch (err) {
      console.error('Ошибка удаления прочитанных:', err);
      return 0;
    }
  };

  // Уникальные категории
  const categories = useMemo(() => {
    const cats = new Set<string>();
    notifications.forEach((n: any) => {
      if (n.category) cats.add(getVerbCategory(n.category));
    });
    return Array.from(cats).sort();
  }, [notifications]);

  // Фильтрация
  const filteredNotifications = useMemo(() => {
    return notifications.filter((n: any) => {
      // Фильтр по прочитанности
      if (filterRead === 'unread' && n.is_read) return false;
      if (filterRead === 'read' && !n.is_read) return false;

      // Фильтр по категории
      if (filterCategory && n.category && getVerbCategory(n.category) !== filterCategory) return false;

      // Поиск
      if (search) {
        const q = search.toLowerCase();
        const title = (n.title || '').toLowerCase();
        const message = (n.message || '').toLowerCase();
        if (!title.includes(q) && !message.includes(q)) return false;
      }

      return true;
    });
  }, [notifications, search, filterRead, filterCategory]);

  const unreadCount = notifications.filter((n: any) => !n.is_read).length;
  const readCount = notifications.filter((n: any) => n.is_read).length;

  // Подсчет уведомлений по категориям
  const categoryCounts = useMemo(() => {
    const counts: Record<string, { total: number; unread: number }> = {};
    
    notifications.forEach((n: any) => {
      if (!n.category) return;
      const category = getVerbCategory(n.category);
      
      if (!counts[category]) {
        counts[category] = { total: 0, unread: 0 };
      }
      
      counts[category].total++;
      if (!n.is_read) {
        counts[category].unread++;
      }
    });
    
    // Сортируем по количеству непрочитанных
    return Object.entries(counts)
      .sort(([, a], [, b]) => b.unread - a.unread || b.total - a.total)
      .map(([category, data]) => ({ category, ...data }));
  }, [notifications]);

  const handleNotificationClick = async (notification: any) => {
    if (!notification.is_read) {
      await markAsRead(notification.id);
    }
    const actionUrl = resolveNotificationActionUrl(notification);
    if (actionUrl) {
      window.location.href = actionUrl;
    }
  };

  const getCategoryIconEmoji = (categoryCode?: string, icon?: string) => {
    // Маппинг категорий на эмодзи
    const iconMap: Record<string, string> = {
      'communications': '💬',
      'messages': '💬',
      'requests': '📝',
      'documents': '📄',
      'calendar': '📅',
      'system': '⚙️',
      'finance': '💰',
      'procurement': '🛒',
      'equipment': '🖥️',
    };
    
    return iconMap[categoryCode || ''] || '📋';
  };

  return (
    <AppShell>
      <section className="mx-auto max-w-5xl app-surface rounded-2xl p-4 sm:p-5">
        {/* Заголовок */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Уведомления</p>
          <div className="flex flex-wrap gap-2">
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
              >
                <CheckCheck size={16} />
                Прочитать все
              </button>
            )}
            {readCount > 0 && (
              <button
                onClick={async () => {
                  const count = await deleteAllRead();
                  if (count > 0) {
                    console.log(`Удалено ${count} прочитанных уведомлений`);
                  }
                }}
                className="app-feedback-danger inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium"
              >
                <Trash2 size={16} />
                Удалить прочитанные
              </button>
            )}
          </div>
        </div>

        {/* Поиск и фильтры */}
        <div className="mb-4 space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по уведомлениям..."
                className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg p-2.5 transition ${
                filtersOpen
                  ? 'app-selected app-accent-text'
                  : 'app-surface-muted app-text-muted hover:bg-[var(--surface-tertiary)]'
              }`}
            >
              <Filter size={16} />
              {(filterRead !== 'all' || filterCategory) && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white">
                  {[filterRead !== 'all', filterCategory].filter(Boolean).length}
                </span>
              )}
            </button>
          </div>

          {filtersOpen && (
            <div className="app-surface-muted flex flex-col gap-2 rounded-xl p-3">
              <select
                value={filterRead}
                onChange={(e) => setFilterRead(e.target.value as any)}
                className="app-select rounded-lg px-3 py-2 text-sm"
              >
                <option value="all">Все уведомления</option>
                <option value="unread">Только непрочитанные</option>
                <option value="read">Только прочитанные</option>
              </select>

              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="app-select rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Все категории</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>

              {(filterRead !== 'all' || filterCategory) && (
                <button
                  type="button"
                  onClick={() => {
                    setFilterRead('all');
                    setFilterCategory('');
                  }}
                  className="app-action-secondary rounded-lg px-3 py-2 text-sm font-medium transition"
                >
                  Очистить фильтры
                </button>
              )}
            </div>
          )}
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {[
            { key: 'all', label: 'Все', count: notifications.length },
            { key: 'unread', label: 'Непрочитанные', count: unreadCount },
            { key: 'read', label: 'Прочитанные', count: readCount },
          ].map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFilterRead(item.key as 'all' | 'unread' | 'read')}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                filterRead === item.key ? 'app-pill-active' : 'app-pill'
              }`}
            >
              <span>{item.label}</span>
              <span className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                filterRead === item.key ? 'app-pill-count-active' : 'app-pill-count'
              }`}>
                {item.count}
              </span>
            </button>
          ))}
        </div>

        {/* Бейджи категорий с счетчиками */}
        {categoryCounts.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2">
            <button
              onClick={() => setFilterCategory('')}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                filterCategory === ''
                  ? 'app-pill-active'
                  : 'app-pill'
              }`}
            >
              <span>Все</span>
              <span className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                filterCategory === ''
                  ? 'app-pill-count-active'
                  : 'app-pill-count'
              }`}>
                {notifications.length}
              </span>
            </button>
            
            {categoryCounts.map(({ category, total, unread }) => (
              <button
                key={category}
                onClick={() => setFilterCategory(filterCategory === category ? '' : category)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  filterCategory === category
                    ? 'app-pill-active'
                    : 'app-pill'
                }`}
              >
                <span>{category}</span>
                <span className={`app-badge inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-bold ${
                  filterCategory === category
                    ? 'app-pill-count-active'
                    : 'app-pill-count'
                }`}>
                  <span>{total}</span>
                  {unread > 0 && (
                    <>
                      <span className="app-text-muted">•</span>
                      <span className="app-accent-text">
                        {unread}
                      </span>
                    </>
                  )}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Список уведомлений */}
        {loading ? (
          <div className="app-surface-muted rounded-xl p-12 text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
            <p className="app-text-muted text-sm">Загрузка уведомлений...</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="app-surface-muted rounded-xl p-12 text-center">
            <Bell size={48} className="app-text-muted mx-auto mb-3 opacity-40" />
            <p className="text-base font-medium text-[var(--foreground)]">
              {search || filterRead !== 'all' || filterCategory
                ? 'Нет уведомлений по заданным критериям'
                : 'Нет уведомлений'}
            </p>
            <p className="app-text-muted mt-1 text-sm">
              {search || filterRead !== 'all' || filterCategory
                ? 'Попробуйте изменить фильтры'
                : 'Все новые уведомления появятся здесь'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredNotifications.map((notification: any) => (
              <article
                key={notification.id}
                className={`group overflow-hidden rounded-xl border transition ${
                  notification.is_read
                    ? 'app-surface hover:border-[var(--border-strong)]'
                    : 'app-unread-surface border-[color:color-mix(in_srgb,var(--accent-primary)_20%,var(--border-subtle))] hover:border-[color:var(--accent-primary)]'
                }`}
              >
                <div className="flex gap-4 p-4">
                  {/* Иконка */}
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xl ${
                      notification.is_read ? 'bg-[var(--surface-secondary)]' : 'bg-[color:color-mix(in_srgb,var(--accent-primary)_14%,var(--surface-primary))]'
                    }`}
                    style={
                      notification.color
                        ? { backgroundColor: notification.color + '20', color: notification.color }
                        : undefined
                    }
                  >
                    {getCategoryIconEmoji(notification.category, notification.icon)}
                  </div>

                  {/* Содержимое */}
                  <div 
                    onClick={() => handleNotificationClick(notification)}
                    className="min-w-0 flex-1 cursor-pointer"
                  >
                    <div className="mb-1 flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-[var(--foreground)] transition group-hover:text-[var(--accent-primary-strong)]">
                        {notification.title || getVerbName(notification.verb || notification.category)}
                      </h3>
                      {!notification.is_read && (
                        <div className="app-dot-accent mt-1.5 h-2 w-2 shrink-0 rounded-full"></div>
                      )}
                    </div>

                    <p className="app-text-muted mb-2 line-clamp-2 text-sm">
                      {notification.short_message || notification.message}
                    </p>

                    <div className="app-text-muted flex items-center gap-3 text-xs">
                      {notification.category && (
                        <span className="app-badge px-2 py-0.5 font-medium">
                          {getVerbCategory(notification.category)}
                        </span>
                      )}
                      <span>
                        {(() => {
                          const timestamp = notification.created_at || notification.timestamp;
                          if (!timestamp) return 'недавно';
                          try {
                            return formatDistanceToNow(new Date(timestamp), {
                              addSuffix: true,
                              locale: ru,
                            });
                          } catch (e) {
                            return 'недавно';
                          }
                        })()}
                      </span>
                    </div>
                  </div>
                  
                  {/* Кнопка удаления */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteNotification(notification.id);
                    }}
                    className="app-action-danger flex-shrink-0 rounded-lg p-2 transition-all"
                    aria-label="Удалить"
                    title="Удалить уведомление"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}
