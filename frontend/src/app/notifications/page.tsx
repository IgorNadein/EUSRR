'use client';

import { AppShell } from '@/components/AppShell';
import { useNotifications } from '@/hooks/useApi';
import { Bell, Check, CheckCheck, Filter, Search, Trash2, Settings } from 'lucide-react';
import { useState, useMemo } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale/ru';
import { getVerbCategory, getVerbName } from '@/lib/verbTranslations';
import Link from 'next/link';

export default function NotificationsPage() {
  const { notifications: notificationsData, loading, markAsRead, markAllAsRead, deleteNotification, deleteAllRead } = useNotifications();
  const notifications = Array.isArray(notificationsData) ? notificationsData : [];

  const [search, setSearch] = useState('');
  const [filterRead, setFilterRead] = useState<'all' | 'unread' | 'read'>('all');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [filtersOpen, setFiltersOpen] = useState(false);

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
    if (notification.action_url) {
      window.location.href = notification.action_url;
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
      <div className="mx-auto max-w-5xl px-4 py-6">
        {/* Заголовок */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Уведомления</h1>
            <p className="mt-1 text-sm text-gray-500">
              {unreadCount > 0 ? `${unreadCount} непрочитанных` : 'Все прочитано'}
            </p>
          </div>
          <div className="flex gap-2">
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 transition"
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
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
              >
                <Trash2 size={16} />
                Удалить прочитанные
              </button>
            )}
            <Link
              href="/notifications/settings"
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
            >
              <Settings size={16} />
              Настройки
            </Link>
          </div>
        </div>

        {/* Поиск и фильтры */}
        <div className="mb-4 space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по уведомлениям..."
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              />
            </div>
            <button
              type="button"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`relative inline-flex items-center justify-center rounded-lg border p-2.5 transition ${
                filtersOpen
                  ? 'border-sky-400 bg-sky-50 text-sky-600'
                  : 'border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100'
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
            <div className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
              <select
                value={filterRead}
                onChange={(e) => setFilterRead(e.target.value as any)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
              >
                <option value="all">Все уведомления</option>
                <option value="unread">Только непрочитанные</option>
                <option value="read">Только прочитанные</option>
              </select>

              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800"
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
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition"
                >
                  Очистить фильтры
                </button>
              )}
            </div>
          )}
        </div>

        {/* Бейджи категорий с счетчиками */}
        {categoryCounts.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2">
            <button
              onClick={() => setFilterCategory('')}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                filterCategory === ''
                  ? 'bg-sky-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <span>Все</span>
              <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                filterCategory === ''
                  ? 'bg-sky-500 text-white'
                  : 'bg-gray-200 text-gray-600'
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
                    ? 'bg-sky-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <span>{category}</span>
                <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                  filterCategory === category
                    ? 'bg-sky-500 text-white'
                    : 'bg-gray-200 text-gray-600'
                }`}>
                  <span>{total}</span>
                  {unread > 0 && (
                    <>
                      <span className={filterCategory === category ? 'text-sky-300' : 'text-gray-400'}>•</span>
                      <span className={filterCategory === category ? 'text-sky-100' : 'text-sky-600'}>
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
          <div className="rounded-xl bg-gray-50 p-12 text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-sky-500"></div>
            <p className="text-sm text-gray-500">Загрузка уведомлений...</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="rounded-xl bg-gray-50 p-12 text-center">
            <Bell size={48} className="mx-auto mb-3 text-gray-300" />
            <p className="text-base font-medium text-gray-700">
              {search || filterRead !== 'all' || filterCategory
                ? 'Нет уведомлений по заданным критериям'
                : 'Нет уведомлений'}
            </p>
            <p className="mt-1 text-sm text-gray-500">
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
                className={`group rounded-xl border transition hover:shadow-md ${
                  notification.is_read
                    ? 'border-gray-200 bg-white'
                    : 'border-sky-200 bg-sky-50/30'
                }`}
              >
                <div className="flex gap-4 p-4">
                  {/* Иконка */}
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xl ${
                      notification.is_read ? 'bg-gray-100' : 'bg-sky-100'
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
                      <h3 className="font-semibold text-gray-900 group-hover:text-sky-600 transition">
                        {notification.title || getVerbName(notification.verb || notification.category)}
                      </h3>
                      {!notification.is_read && (
                        <div className="h-2 w-2 shrink-0 rounded-full bg-sky-500 mt-1.5"></div>
                      )}
                    </div>

                    <p className="mb-2 text-sm text-gray-600 line-clamp-2">
                      {notification.short_message || notification.message}
                    </p>

                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      {notification.category && (
                        <span className="rounded bg-gray-100 px-2 py-0.5 font-medium text-gray-600">
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
                    className="opacity-0 group-hover:opacity-100 p-2 hover:bg-red-50 rounded-lg transition-all flex-shrink-0"
                    aria-label="Удалить"
                    title="Удалить уведомление"
                  >
                    <Trash2 size={18} className="text-gray-400 hover:text-red-600" />
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
