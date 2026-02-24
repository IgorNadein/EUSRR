"use client";

import { Bell, Building2, CalendarDays, ChevronLeft, ChevronRight, FileSignature, FileText, Home as HomeIcon, Menu, MessageSquare, Plus, Search, Trash2, Users, Wallet, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { CalendarProvider, useCalendar } from "@/contexts/CalendarContext";
import { CalendarModal } from "@/components/CalendarModal";

type AppShellProps = {
  children: ReactNode;
};

type PageHeaderProps = {
  title: string;
  subtitle?: string;
  badge?: string;
  eyebrow?: string;
};

type HeaderProps = {
  onOpenLeftNav: () => void;
  onOpenCalendar: () => void;
};

type LeftNavContentProps = {
  onNavigate?: () => void;
};

const navItems = [
  { href: "/", label: "Лента", icon: HomeIcon },
  { href: "/messages", label: "Сообщения", icon: MessageSquare },
  { href: "/calendar", label: "Календарь", icon: CalendarDays },
  { href: "/employees", label: "Сотрудники", icon: Users },
  { href: "/departments", label: "Отделы", icon: Building2 },
  { href: "/requests", label: "Заявления", icon: FileSignature },
  { href: "/documents", label: "Документы", icon: FileText },
  { href: "/finances", label: "Финансы", icon: Wallet },
];

const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

type SidebarCalendarEvent = {
  id: number;
  title: string;
  start?: string | null;
  end?: string | null;
  allDay?: boolean;
  color?: string | null;
};

const pad = (v: number) => String(v).padStart(2, "0");

const formatDateKey = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

const startOfWeekMonday = (date: Date) => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const dayIndex = (d.getDay() + 6) % 7; // Пн = 0
  d.setDate(d.getDate() - dayIndex);
  return d;
};

const sameDate = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

function Header({ onOpenLeftNav, onOpenCalendar }: HeaderProps) {
  const router = useRouter();
  const { user, logout } = useUser();
  const [searchQuery, setSearchQuery] = useState("");
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  // Закрытие меню при клике вне
  useEffect(() => {
    if (!userMenuOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const desktop = document.getElementById("user-menu-root");
      const mobile = document.getElementById("user-menu-root-mobile");
      const insideDesktop = desktop && desktop.contains(target);
      const insideMobile = mobile && mobile.contains(target);
      if (!insideDesktop && !insideMobile) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [userMenuOpen]);

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  const submitSearch = () => {
    const query = searchQuery.trim();
    if (!query) return;
    router.push(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <header className="sticky top-0 z-[40] border-b border-slate-100 bg-white/90 backdrop-blur">
      <div className="mx-auto max-w-6xl px-4 sm:px-8">
        <div className="flex h-14 items-center justify-between gap-3">
          <button
            type="button"
            onClick={onOpenLeftNav}
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100 lg:hidden"
            aria-label="Открыть левое меню"
          >
            <Menu size={20} className="text-gray-700" />
          </button>

          <Link href="/" className="flex items-center justify-center">
            <img src="/logo.png" alt="Логотип" className="h-10 w-auto lg:h-11" />
          </Link>

          <button
            type="button"
            onClick={onOpenCalendar}
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100 lg:hidden"
            aria-label="Открыть календарь"
          >
            <CalendarDays size={20} className="text-gray-700" />
          </button>

          <div className="hidden flex-1 items-center justify-center lg:flex">
            <div className="relative w-full max-w-xl">
              <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submitSearch();
                  }
                }}
                className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-11 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="Поиск"
              />
            </div>
          </div>

          <div className="ml-auto hidden items-center gap-1 sm:gap-2 lg:flex">
            <button className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100">
              <Bell size={18} className="text-gray-600" />
            </button>
            <div className="ml-1 relative h-10 w-10" id="user-menu-root">
              <div
                className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white hover:bg-sky-500 cursor-pointer"
                title={userName}
                onClick={() => setUserMenuOpen((v) => !v)}
              >
                {user?.avatar ? (
                  <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                ) : (
                  userInitials
                )}
              </div>
              {user?.is_active ? (
                <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
              ) : null}
              {/* Меню пользователя */}
              {userMenuOpen && (
                <div className="absolute right-0 top-12 z-[60] w-48 rounded-xl bg-white py-2 shadow-lg ring-1 ring-slate-100 animate-fade-in">
                  <button
                    className="w-full text-left px-4 py-2 text-sm hover:bg-sky-50"
                    onClick={() => { setUserMenuOpen(false); router.push('/profile'); }}
                  >Мой профиль</button>
                  <button
                    className="w-full text-left px-4 py-2 text-sm hover:bg-sky-50"
                    onClick={() => { setUserMenuOpen(false); router.push('/settings'); }}
                  >Настройки</button>
                  <div className="my-1 border-t border-slate-100" />
                  <button
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                    onClick={() => { setUserMenuOpen(false); logout(); }}
                  >Выйти</button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="pb-3 lg:hidden">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-gray-200 bg-gray-50 hover:bg-slate-100"
              aria-label="Уведомления"
            >
              <Bell size={18} className="text-gray-600" />
            </button>

            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submitSearch();
                  }
                }}
                className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-10 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="Поиск"
              />
            </div>

            <div className="relative h-10 w-10" id="user-menu-root-mobile">
              <div
                className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white hover:bg-sky-500 cursor-pointer"
                title={userName}
                onClick={() => setUserMenuOpen((v) => !v)}
              >
                {user?.avatar ? (
                  <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                ) : (
                  userInitials
                )}
              </div>
              {user?.is_active ? (
                <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
              ) : null}
              {/* Меню пользователя */}
              {userMenuOpen && (
                <div className="absolute right-0 top-12 z-[60] w-48 rounded-xl bg-white py-2 shadow-lg ring-1 ring-slate-100 animate-fade-in">
                  <button
                    className="w-full text-left px-4 py-2 text-sm hover:bg-sky-50"
                    onClick={() => { setUserMenuOpen(false); router.push('/profile'); }}
                  >Мой профиль</button>
                  <button
                    className="w-full text-left px-4 py-2 text-sm hover:bg-sky-50"
                    onClick={() => { setUserMenuOpen(false); router.push('/settings'); }}
                  >Настройки</button>
                  <div className="my-1 border-t border-slate-100" />
                  <button
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                    onClick={() => { setUserMenuOpen(false); logout(); }}
                  >Выйти</button>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </header>
  );
}

function LeftNavContent({ onNavigate }: LeftNavContentProps) {
  const pathname = usePathname();

  const navLinkClass = (href: string) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50 ${pathname === href ? "bg-sky-50 text-sky-700 ring-1 ring-sky-100" : "text-gray-700"
    }`;

  const navIconClass = (href: string) => (pathname === href ? "text-sky-700" : "text-gray-400");

  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="space-y-2 text-sm text-gray-700">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={navLinkClass(href)} onClick={onNavigate}>
            <Icon size={18} className={navIconClass(href)} />
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

function LeftNav() {
  return (
    <aside className="hidden w-64 flex-shrink-0 lg:block lg:sticky lg:self-start lg:top-22 lg:max-h-[calc(100vh-5.5rem)] lg:overflow-y-auto">
      <div className="space-y-4 lg:pb-2">
        <LeftNavContent />
      </div>
    </aside>
  );
}

function CalendarCard({ 
  onOpenCalendarModal,
  onOpenEventModal
}: { 
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (event: any, date?: Date) => void;
}) {
  const { calendars, selectedCalendarId, setSelectedCalendarId, loading: calendarsLoading, reloadCalendars } = useCalendar();
  
  const [monthDate, setMonthDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [events, setEvents] = useState<SidebarCalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);

  // Загрузка событий выбранного календаря
  useEffect(() => {
    if (selectedCalendarId === null) {
      setEvents([]);
      return;
    }

    let cancelled = false;

    const start = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const end = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 1);
    const weekStart = startOfWeekMonday(new Date());
    const weekEndExclusive = new Date(weekStart);
    weekEndExclusive.setDate(weekEndExclusive.getDate() + 7);

    const fetchStart = weekStart < start ? weekStart : start;
    const fetchEnd = weekEndExclusive > end ? weekEndExclusive : end;

    async function loadCalendarEvents() {
      try {
        setLoading(true);
        setError(null);

        const result = await apiClient.getCalendarEvents({
          start: formatDateKey(fetchStart),
          end: formatDateKey(fetchEnd),
          calendar: selectedCalendarId ?? undefined,
        });

        if (!cancelled) {
          const eventsList = Array.isArray(result) ? result : (result?.results || []);
          setEvents(eventsList);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err || "");
          const isNetworkLike = message === "NetworkError" || /fetch failed/i.test(message);
          if (!isNetworkLike) {
            console.error("Ошибка загрузки событий календаря:", err);
          }
          setError("Не удалось загрузить события");
          setEvents([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCalendarEvents();

    return () => {
      cancelled = true;
    };
  }, [monthDate, selectedCalendarId]);

  const monthLabel = useMemo(() => {
    const label = monthDate.toLocaleDateString("ru-RU", {
      month: "long",
      year: "numeric",
    });
    return label.charAt(0).toUpperCase() + label.slice(1);
  }, [monthDate]);

  // Обработчики календарей
  const handleCreateCalendar = () => {
    onOpenCalendarModal({ name: "" });
  };

  // Обработчики событий
  const handleDayClick = (date: Date) => {
    if (!selectedCalendarId) {
      alert("Сначала выберите календарь");
      return;
    }
    setSelectedDate(date);
    const startDate = new Date(date);
    startDate.setHours(10, 0, 0, 0);
    const endDate = new Date(date);
    endDate.setHours(11, 0, 0, 0);
    
    const newEvent = {
      title: "",
      description: "",
      start: startDate.toISOString(),
      end: endDate.toISOString(),
      calendar: selectedCalendarId,
      color_event: "#3498db",
    };
    onOpenEventModal(newEvent, date);
  };

  const handleEventClick = async (eventId: number) => {
    try {
      const event = await apiClient.getEvent(eventId);
      onOpenEventModal(event);
    } catch (err) {
      console.error("Ошибка загрузки события:", err);
    }
  };

  const eventDays = useMemo(() => {
    const days = new Set<string>();
    events.forEach((ev) => {
      if (!ev.start) return;
      const start = new Date(ev.start);
      if (Number.isNaN(start.getTime())) return;
      days.add(formatDateKey(start));
    });
    return days;
  }, [events]);

  const days = useMemo(() => {
    const firstOfMonth = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const weekDayIndex = (firstOfMonth.getDay() + 6) % 7;
    const gridStart = new Date(firstOfMonth);
    gridStart.setDate(firstOfMonth.getDate() - weekDayIndex);

    const today = new Date();

    return Array.from({ length: 42 }, (_, i) => {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + i);

      const key = formatDateKey(date);
      return {
        key,
        day: date.getDate(),
        date,
        inCurrentMonth: date.getMonth() === monthDate.getMonth(),
        isToday: sameDate(date, today),
        hasEvents: eventDays.has(key),
      };
    });
  }, [monthDate, eventDays]);

  const weekEvents = useMemo(() => {
    const weekStart = startOfWeekMonday(new Date());
    const weekEndExclusive = new Date(weekStart);
    weekEndExclusive.setDate(weekEndExclusive.getDate() + 7);

    return [...events]
      .filter((ev) => ev.start)
      .filter((ev) => {
        const start = new Date(ev.start || "");
        if (Number.isNaN(start.getTime())) return false;
        return start >= weekStart && start < weekEndExclusive;
      })
      .sort((a, b) => new Date(a.start || "").getTime() - new Date(b.start || "").getTime())
      .slice(0, 12);
  }, [events]);

  return (
    <>
      <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Календарь</p>
          <button
            onClick={handleCreateCalendar}
            className="flex h-6 w-6 items-center justify-center rounded-full hover:bg-gray-100 transition"
            title="Создать календарь"
          >
            <Plus size={14} className="text-gray-600" />
          </button>
        </div>
        {calendars.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
            <p className="mb-2 text-xs font-medium text-gray-700">Календарей пока нет</p>
            <button
              onClick={handleCreateCalendar}
              className="w-full rounded-md bg-sky-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-600"
            >
              Создать первый календарь
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <select
              value={selectedCalendarId || ""}
              onChange={(e) => setSelectedCalendarId(Number(e.target.value))}
              className="flex-1 rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-xs text-gray-800 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {calendars.map((cal) => (
                <option key={cal.id} value={cal.id}>
                  {cal.name}
                </option>
              ))}
            </select>
            {selectedCalendarId && (
              <button
                onClick={() => {
                  const cal = calendars.find(c => c.id === selectedCalendarId);
                  if (cal) {
                    onOpenCalendarModal(cal);
                  }
                }}
                className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-gray-100 transition"
                title="Настройки календаря"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="1"></circle>
                  <circle cx="12" cy="5" r="1"></circle>
                  <circle cx="12" cy="19" r="1"></circle>
                </svg>
              </button>
            )}
          </div>
        )}
      </div>

      <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="flex items-center justify-between text-sm font-semibold text-gray-900">
        <span>Месяц</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1))}
            className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-slate-100"
            aria-label="Предыдущий месяц"
          >
            <ChevronLeft size={16} className="text-gray-600" />
          </button>
          <span className="min-w-28 text-center text-xs font-normal text-gray-500">{monthLabel}</span>
          <button
            type="button"
            onClick={() => setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1))}
            className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-slate-100"
            aria-label="Следующий месяц"
          >
            <ChevronRight size={16} className="text-gray-600" />
          </button>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs text-gray-500">
        {weekdays.map((day) => (
          <div key={day} className="py-1 font-medium">
            {day}
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1 text-sm text-gray-800">
        {days.map((day) => (
          <button
            key={day.key}
            type="button"
            onClick={() => day.inCurrentMonth && handleDayClick(day.date)}
            disabled={!day.inCurrentMonth}
            className={`relative flex h-9 items-center justify-center rounded-full transition ${
              day.isToday
                ? "bg-sky-100 text-sky-800 font-semibold ring-1 ring-sky-200"
                : day.inCurrentMonth
                  ? "hover:bg-sky-50 cursor-pointer"
                  : "text-gray-300 cursor-default"
            }`}
          >
            {day.day}
            {day.hasEvents && day.inCurrentMonth ? (
              <span className="absolute bottom-1 h-1.5 w-1.5 rounded-full bg-sky-500" />
            ) : null}
          </button>
        ))}
      </div>
      </div>

      <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">На этой неделе</p>
        {loading ? (
          <p className="text-xs text-gray-500">Загрузка...</p>
        ) : error ? (
          <p className="text-xs text-red-600">{error}</p>
        ) : weekEvents.length === 0 ? (
          <p className="text-xs text-gray-500">Событий нет</p>
        ) : (
          <div className="space-y-2">
            {weekEvents.map((event) => {
              const start = event.start ? new Date(event.start) : null;
              const dateLabel = start && !Number.isNaN(start.getTime())
                ? start.toLocaleString("ru-RU", {
                    weekday: "short",
                    day: "2-digit",
                    month: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "Без даты";

              return (
                <button
                  key={`${event.id}-${event.start || ""}`}
                  type="button"
                  onClick={() => handleEventClick(event.id)}
                  className="w-full rounded-lg bg-gray-50 px-2.5 py-2 text-left transition hover:bg-gray-100"
                >
                  <p className="truncate text-xs font-medium text-gray-800">{event.title}</p>
                  <p className="mt-0.5 text-[11px] text-gray-500">{dateLabel}</p>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

function Calendar({ 
  onOpenCalendarModal,
  onOpenEventModal
}: { 
  onOpenCalendarModal: (calendar?: { id?: number; name: string }) => void;
  onOpenEventModal: (event: any, date?: Date) => void;
}) {
  return (
    <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block">
      <div className="sticky top-22 space-y-4 lg:pb-2 max-h-[calc(100vh-5.5rem)] overflow-y-auto">
        <CalendarCard 
          onOpenCalendarModal={onOpenCalendarModal}
          onOpenEventModal={onOpenEventModal}
        />
      </div>
    </aside>
  );
}

export function PageHeader({ title, subtitle, badge, eyebrow = "Раздел" }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-sky-600">{eyebrow}</p>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        </div>
        {badge ? (
          <div className="rounded-full bg-sky-50 px-4 py-2 text-xs font-medium text-sky-700 ring-1 ring-sky-100">{badge}</div>
        ) : null}
      </div>
      {subtitle ? <p className="text-sm text-gray-600">{subtitle}</p> : null}
    </div>
  );
}

export function AppShell({ children }: AppShellProps) {
  const { user, loading } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const isMessageDialogPage = pathname.startsWith('/messages/') && pathname !== '/messages';

  const [isMobileLeftNavOpen, setIsMobileLeftNavOpen] = useState(false);
  const [isMobileCalendarOpen, setIsMobileCalendarOpen] = useState(false);

  // Состояния модалов календаря
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [showEventModal, setShowEventModal] = useState(false);
  const [editingCalendar, setEditingCalendar] = useState<{ id?: number; name: string } | null>(null);
  const [editingEvent, setEditingEvent] = useState<any>(null);

  // Обработчики модалов
  const handleOpenCalendarModal = (calendar?: { id?: number; name: string }) => {
    setEditingCalendar(calendar || { name: "" });
    setShowCalendarModal(true);
  };

  const handleOpenEventModal = (event: any, date?: Date) => {
    setEditingEvent(event);
    setShowEventModal(true);
  };

  useEffect(() => {
    // Если загрузка завершена и пользователь не авторизован - редирект на логин
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    setIsMobileLeftNavOpen(false);
    setIsMobileCalendarOpen(false);
  }, [pathname]);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1024) {
        setIsMobileLeftNavOpen(false);
        setIsMobileCalendarOpen(false);
      }
    };

    window.addEventListener("resize", onResize);
    onResize();

    return () => {
      window.removeEventListener("resize", onResize);
    };
  }, []);

  useEffect(() => {
    if (isMobileLeftNavOpen || isMobileCalendarOpen) {
      document.body.style.overflow = "hidden";
      return;
    }

    document.body.style.overflow = "";

    return () => {
      document.body.style.overflow = "";
    };
  }, [isMobileLeftNavOpen, isMobileCalendarOpen]);

  // Показываем загрузку, пока проверяем авторизацию
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-white flex items-center justify-center">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-sky-400 border-t-transparent"></div>
          <p className="text-sm text-gray-500">Загрузка...</p>
        </div>
      </div>
    );
  }

  // Если пользователь не авторизован, ничего не показываем (уже редиректим)
  if (!user) {
    return null;
  }

  return (
    <CalendarProvider>
      <div className={`${isMessageDialogPage ? 'h-[100dvh] overflow-hidden' : 'min-h-screen'} bg-gradient-to-b from-sky-50 via-white to-white text-gray-900 flex flex-col`}>
        <Header onOpenLeftNav={() => setIsMobileLeftNavOpen(true)} onOpenCalendar={() => setIsMobileCalendarOpen(true)} />
      <div className="mx-auto flex w-full flex-1 min-h-0 max-w-6xl gap-6 px-4 py-6 sm:px-8 lg:py-8">
        <LeftNav />
        <main className={`flex-1 min-w-0 min-h-0 space-y-6 ${isMessageDialogPage ? 'overflow-visible' : ''}`}>{children}</main>
        <Calendar 
          onOpenCalendarModal={handleOpenCalendarModal}
          onOpenEventModal={handleOpenEventModal}
        />
      </div>

      <div className={`fixed inset-0 z-[100] lg:hidden ${isMobileLeftNavOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
        <button
          type="button"
          className={`absolute inset-0 bg-black/40 transition-opacity ${isMobileLeftNavOpen ? "opacity-100" : "opacity-0"}`}
          onClick={() => setIsMobileLeftNavOpen(false)}
          aria-label="Закрыть левое меню"
        />
        <div
          className={`absolute inset-y-0 left-0 w-full overflow-y-auto bg-white p-4 transition-transform duration-300 ${
            isMobileLeftNavOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-900">Меню</p>
            <button
              type="button"
              onClick={() => setIsMobileLeftNavOpen(false)}
              className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
              aria-label="Закрыть меню"
            >
              <X size={20} className="text-gray-700" />
            </button>
          </div>
          <LeftNavContent onNavigate={() => setIsMobileLeftNavOpen(false)} />
        </div>
      </div>

      <div className={`fixed inset-0 z-[100] lg:hidden ${isMobileCalendarOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
        <button
          type="button"
          className={`absolute inset-0 bg-black/40 transition-opacity ${isMobileCalendarOpen ? "opacity-100" : "opacity-0"}`}
          onClick={() => setIsMobileCalendarOpen(false)}
          aria-label="Закрыть календарь"
        />
        <div
          className={`absolute inset-y-0 right-0 w-full overflow-y-auto bg-white p-4 transition-transform duration-300 ${
            isMobileCalendarOpen ? "translate-x-0" : "translate-x-full"
          }`}
        >
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-900">Календарь</p>
            <button
              type="button"
              onClick={() => setIsMobileCalendarOpen(false)}
              className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
              aria-label="Закрыть календарь"
            >
              <X size={20} className="text-gray-700" />
            </button>
          </div>
          <CalendarCard 
            onOpenCalendarModal={handleOpenCalendarModal}
            onOpenEventModal={handleOpenEventModal}
          />
        </div>
      </div>

      {/* Модалы календаря - рендерятся на верхнем уровне */}
      <CalendarModal
        isOpen={showCalendarModal}
        onClose={() => {
          setShowCalendarModal(false);
          setEditingCalendar(null);
        }}
        calendar={editingCalendar}
      />

      {/* Модальное окно события */}
      {showEventModal && editingEvent && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                {editingEvent.id ? "Редактировать событие" : "Создать событие"}
              </h3>
              <button
                onClick={() => {
                  setShowEventModal(false);
                  setEditingEvent(null);
                }}
                className="rounded-full p-1 hover:bg-gray-100"
              >
                <X size={20} className="text-gray-600" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Название
                </label>
                <input
                  type="text"
                  value={editingEvent.title}
                  onChange={(e) => setEditingEvent({ ...editingEvent, title: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  placeholder="Название события"
                  autoFocus
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Описание
                </label>
                <textarea
                  value={editingEvent.description || ""}
                  onChange={(e) => setEditingEvent({ ...editingEvent, description: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  placeholder="Описание (необязательно)"
                  rows={3}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Начало</label>
                  <input
                    type="datetime-local"
                    value={editingEvent.start ? new Date(editingEvent.start).toISOString().slice(0, 16) : ""}
                    onChange={(e) => setEditingEvent({ ...editingEvent, start: new Date(e.target.value).toISOString() })}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Конец</label>
                  <input
                    type="datetime-local"
                    value={editingEvent.end ? new Date(editingEvent.end).toISOString().slice(0, 16) : ""}
                    onChange={(e) => setEditingEvent({ ...editingEvent, end: new Date(e.target.value).toISOString() })}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Цвет
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={editingEvent.color_event || "#3498db"}
                    onChange={(e) => setEditingEvent({ ...editingEvent, color_event: e.target.value })}
                    className="h-10 w-20 rounded-lg border border-gray-300 cursor-pointer"
                  />
                  <span className="text-xs text-gray-500">{editingEvent.color_event || "#3498db"}</span>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    if (!editingEvent.title.trim()) return;
                    try {
                      if (editingEvent.id) {
                        await apiClient.updateEvent(editingEvent.id, {
                          title: editingEvent.title,
                          description: editingEvent.description,
                          start: editingEvent.start,
                          end: editingEvent.end,
                          color_event: editingEvent.color_event,
                        });
                      } else {
                        await apiClient.createEvent(editingEvent);
                      }
                      setShowEventModal(false);
                      setEditingEvent(null);
                      // Обновление событий через контекст будет автоматическим
                    } catch (err) {
                      console.error("Ошибка сохранения события:", err);
                      alert("Не удалось сохранить событие");
                    }
                  }}
                  disabled={!editingEvent.title?.trim()}
                  className="flex-1 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {editingEvent.id ? "Сохранить" : "Создать"}
                </button>

                {editingEvent.id && (
                  <button
                    onClick={async () => {
                      if (!confirm(`Удалить событие "${editingEvent.title}"?`)) return;
                      try {
                        await apiClient.deleteEvent(editingEvent.id);
                        setShowEventModal(false);
                        setEditingEvent(null);
                      } catch (err) {
                        console.error("Ошибка удаления события:", err);
                        alert("Не удалось удалить событие");
                      }
                    }}
                    className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-100"
                    title="Удалить событие"
                  >
                    <Trash2 size={16} />
                  </button>
                )}              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </CalendarProvider>
  );
}
