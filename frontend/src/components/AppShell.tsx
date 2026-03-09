"use client";

import { Bell, Building2, CalendarDays, ChevronDown, FileSignature, FileText, Home as HomeIcon, Menu, MessageSquare, Monitor, Search, ShoppingCart, Users, Wallet, X, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useRef, useState, useCallback, useMemo } from "react";
import { apiClient } from "@/lib/api";
import { useUser } from "@/contexts/UserContext";
import { useNotifications } from "@/hooks/useApi";
import { getVerbCategory } from "@/lib/verbTranslations";
import { CalendarModal } from "@/components/CalendarModal";
import CalendarParticipantsModal from "@/components/CalendarParticipantsModal";
import { NotificationCenter, NotificationPanel } from "@/components/NotificationCenter";
import { EventModal } from "@/components/EventModal";
import { ViewDayEventsModal } from "@/components/ViewDayEventsModal";
import { ViewEventDetailsModal } from "@/components/ViewEventDetailsModal";
import { CalendarSidebar } from "@/components/calendar/CalendarSidebar";
import { CalendarCard } from "@/components/calendar/CalendarCard";
import type { CalendarEvent } from "@/services/calendarService";

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
  { href: "/", label: "Лента", icon: HomeIcon, category: "Новости" },
  { href: "/messages", label: "Сообщения", icon: MessageSquare, category: "Сообщения" },
  { href: "/employees", label: "Сотрудники", icon: Users },
  { href: "/departments", label: "Отделы", icon: Building2 },
  { href: "/requests", label: "Заявления", icon: FileSignature, category: "Заявки" },
  { href: "/equipment", label: "Оборудование", icon: Monitor },
  { href: "/procurement", label: "Закупки", icon: ShoppingCart, category: "Закупки" },
  { href: "/documents", label: "Документы", icon: FileText, category: "Документы" },
  { href: "/finances", label: "Финансы", icon: Wallet },
];

function Header({ onOpenLeftNav, onOpenCalendar }: HeaderProps) {
  const router = useRouter();
  const { user, logout } = useUser();
  const [searchQuery, setSearchQuery] = useState("");
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

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
        <div className="flex h-8 lg:h-14 items-center justify-between gap-3">
          <button
            type="button"
            onClick={onOpenLeftNav}
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100 lg:hidden"
            aria-label="Открыть левое меню"
          >
            <Menu size={20} className="text-gray-700"/>
          </button>

          <button
            type="button"
            onClick={() => {
              setIsSearchOpen((v) => {
                if (!v) setTimeout(() => searchInputRef.current?.focus(), 50);
                return !v;
              });
              setIsNotificationsOpen(false);
            }}
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100 lg:hidden"
            aria-label="Поиск"
          >
            <Search size={20} className="text-gray-700" />
          </button>

          <Link href="/" className="flex items-center justify-center">
            <img src="/logo.png" alt="Логотип" className="mt-3 lg:mt-0 h-10 w-auto lg:h-11 bg-white lg:bg-transparent rounded pb-0.5 lg:pb-0" />
          </Link>

          <div className="lg:hidden">
            <NotificationCenter variant="mobile" isOpen={isNotificationsOpen} onToggle={() => {
              setIsNotificationsOpen((v) => !v);
              setIsSearchOpen(false);
            }} />
          </div>

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
            <NotificationCenter />
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

        {/* Мобильная строка поиска */}
        <div
          className={`overflow-hidden transition-all duration-300 lg:hidden ${
            isSearchOpen ? "max-h-20 pb-3" : "max-h-0"
          }`}
        >
          <div className="relative">
            <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  submitSearch();
                  setIsSearchOpen(false);
                }
                if (e.key === "Escape") {
                  setIsSearchOpen(false);
                }
              }}
              className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-11 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              placeholder="Поиск по сайту..."
            />
          </div>
        </div>

        {/* Мобильная панель уведомлений */}
        <div
          className={`overflow-hidden transition-all duration-300 lg:hidden ${
            isNotificationsOpen ? "max-h-[70vh] pb-3" : "max-h-0"
          }`}
        >
          {isNotificationsOpen && (
            <NotificationPanel onClose={() => setIsNotificationsOpen(false)} />
          )}
        </div>

      </div>
    </header>
  );
}

function LeftNavContent({ onNavigate }: LeftNavContentProps) {
  const pathname = usePathname();
  const { notifications: notificationsData } = useNotifications();
  const notifications = Array.isArray(notificationsData) ? notificationsData : [];

  // Подсчет уведомлений по категориям
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    
    notifications.forEach((n: any) => {
      if (!n.category || n.is_read) return; // Только непрочитанные
      const category = getVerbCategory(n.category);
      counts[category] = (counts[category] || 0) + 1;
    });
    
    return counts;
  }, [notifications]);

  const navLinkClass = (href: string) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50 ${pathname === href ? "bg-sky-50 text-sky-700 ring-1 ring-sky-100" : "text-gray-700"
    }`;

  const navIconClass = (href: string) => (pathname === href ? "text-sky-700" : "text-gray-400");

  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="space-y-2 text-sm text-gray-700">
        {navItems.map(({ href, label, icon: Icon, category }) => {
          const count = category ? categoryCounts[category] || 0 : 0;
          
          return (
            <Link key={href} href={href} className={navLinkClass(href)} onClick={onNavigate}>
              <Icon size={18} className={navIconClass(href)} />
              <span className="flex-1">{label}</span>
              {count > 0 && (
                <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-sky-500 px-1.5 text-[10px] font-bold text-white">
                  {count > 99 ? '99+' : count}
                </span>
              )}
            </Link>
          );
        })}
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
  const { user, loading, logout } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const isMessageDialogPage = pathname.startsWith('/messages/') && pathname !== '/messages';

  // Вычисляем данные пользователя один раз на уровне AppShell
  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  const [isMobileLeftNavOpen, setIsMobileLeftNavOpen] = useState(false);
  const [isMobileCalendarOpen, setIsMobileCalendarOpen] = useState(false);
  const [isProfileExpanded, setIsProfileExpanded] = useState(false);

  // Состояния модалов календаря
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [showEventModal, setShowEventModal] = useState(false);
  const [showParticipantsModal, setShowParticipantsModal] = useState(false);
  const [editingCalendar, setEditingCalendar] = useState<{ id?: number; name: string } | null>(null);
  const [editingEvent, setEditingEvent] = useState<any>(null);
  const [participantsCalendar, setParticipantsCalendar] = useState<{ id: number; name: string; user_role?: string } | null>(null);
  const [eventsRefreshTrigger, setEventsRefreshTrigger] = useState(0);
  
  // Новые модалы для просмотра
  const [showDayEventsModal, setShowDayEventsModal] = useState(false);
  const [selectedDateForModal, setSelectedDateForModal] = useState<Date | null>(null);
  const [showEventDetailsModal, setShowEventDetailsModal] = useState(false);
  const [viewingEvent, setViewingEvent] = useState<any>(null);
  const [sidebarEvents, setSidebarEvents] = useState<CalendarEvent[]>([]);
  const [currentSelectedCalendarId, setCurrentSelectedCalendarId] = useState<number | null>(null);

  // Мемоизированные callback'и для предотвращения ререндеров CalendarCard
  const handleSetSidebarEvents = useCallback((events: CalendarEvent[]) => {
    setSidebarEvents(events);
  }, []);

  const handleCalendarChange = useCallback((calendarId: number | null) => {
    setCurrentSelectedCalendarId(calendarId);
  }, []);

  const handleSetEventsRefreshTrigger = useCallback((value: number | ((prev: number) => number)) => {
    setEventsRefreshTrigger(value);
  }, []);

  // Обработчики модалов (мемоизированные для предотвращения ререндеров)
  const handleOpenCalendarModal = useCallback((calendar?: { id?: number; name: string }) => {
    setEditingCalendar(calendar || { name: "" });
    setShowCalendarModal(true);
  }, []);

  const handleOpenEventModal = useCallback((event: any, date?: Date) => {
    // Если передана дата (клик на дату), открываем модал просмотра дня
    if (date && !event.id) {
      setSelectedDateForModal(date);
      setShowDayEventsModal(true);
    } 
    // Если передано событие с id (клик на событие), открываем детали
    else if (event.id) {
      setViewingEvent(event);
      setShowEventDetailsModal(true);
    }
    // Fallback - создание нового события
    else {
      setEditingEvent(event);
      setShowEventModal(true);
    }
  }, []);

  // Создание события из модала просмотра дня
  const handleCreateEventFromDay = useCallback(() => {
    if (!currentSelectedCalendarId) {
      alert("Сначала выберите календарь");
      return;
    }

    if (!selectedDateForModal) return;

    const startDate = new Date(selectedDateForModal);
    startDate.setHours(10, 0, 0, 0);
    const endDate = new Date(selectedDateForModal);
    endDate.setHours(11, 0, 0, 0);

    setEditingEvent({
      title: "",
      description: "",
      start: startDate.toISOString(),
      end: endDate.toISOString(),
      calendar: currentSelectedCalendarId,
      color_event: "#3498db",
    });
    
    setShowDayEventsModal(false);
    setShowEventModal(true);
  }, [currentSelectedCalendarId, selectedDateForModal]);

  // Переход к редактированию из модала просмотра
  const handleEditFromDetails = useCallback(() => {
    setEditingEvent(viewingEvent);
    setShowEventDetailsModal(false);
    setShowEventModal(true);
  }, [viewingEvent]);

  // Клик на событие из модала просмотра дня
  const handleEventClickFromDay = useCallback(async (event: any) => {
    setShowDayEventsModal(false);
    
    // Если это occurrence, загружаем базовое событие
    if (event.is_recurring && event.event_id) {
      try {
        const fullEvent = await apiClient.getEvent(event.event_id);
        setViewingEvent({
          ...fullEvent,
          start: event.start,
          end: event.end,
        });
        setShowEventDetailsModal(true);
      } catch (err) {
        console.error("Ошибка загрузки события:", err);
      }
    } else {
      setViewingEvent(event);
      setShowEventDetailsModal(true);
    }
  }, []);

  const handleEventSaved = useCallback(() => {
    // Обновляем список событий в CalendarCard
    setEventsRefreshTrigger(prev => prev + 1);
  }, []);

  const handleOpenParticipantsModal = useCallback((calendar: { id: number; name: string; user_role?: string }) => {
    setParticipantsCalendar(calendar);
    setShowParticipantsModal(true);
  }, []);

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
    <div className={`${isMessageDialogPage ? 'h-[100dvh] overflow-hidden' : 'min-h-screen'} bg-gradient-to-b from-sky-50 via-white to-white text-gray-900 flex flex-col`}>
        <Header onOpenLeftNav={() => setIsMobileLeftNavOpen(true)} onOpenCalendar={() => setIsMobileCalendarOpen(true)} />
        <div className="mx-auto flex w-full flex-1 min-h-0 max-w-6xl gap-6 px-4 py-4 sm:px-8 lg:py-8">
          <LeftNav />
          <main className={`flex-1 min-w-0 min-h-0 space-y-6 ${isMessageDialogPage ? 'overflow-visible' : ''}`}>{children}</main>
          <CalendarSidebar
            onOpenCalendarModal={handleOpenCalendarModal}
            onOpenEventModal={handleOpenEventModal}
            onOpenParticipantsModal={handleOpenParticipantsModal}
            eventsRefreshTrigger={eventsRefreshTrigger}
            setEventsRefreshTrigger={handleSetEventsRefreshTrigger}
            setSidebarEvents={handleSetSidebarEvents}
            onCalendarChange={handleCalendarChange}
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
            className={`absolute inset-y-0 left-0 w-full overflow-y-auto bg-white p-4 transition-transform duration-300 ${isMobileLeftNavOpen ? "translate-x-0" : "-translate-x-full"
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

            {/* Профиль пользователя */}
            <div className="mb-6 rounded-xl bg-gradient-to-br from-sky-50 to-sky-100 ring-1 ring-sky-100 overflow-hidden">
              <button
                onClick={() => setIsProfileExpanded(!isProfileExpanded)}
                className="w-full flex items-center gap-3 p-4 hover:bg-sky-200/50 transition-colors"
              >
                <div className="h-12 w-12 overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white flex items-center justify-center flex-shrink-0">
                  {user?.avatar ? (
                    <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                  ) : (
                    userInitials
                  )}
                </div>
                <div className="min-w-0 flex-1 text-left">
                  <p className="text-sm font-semibold text-gray-900">{userName}</p>
                  {user?.is_active && (
                    <p className="text-xs text-sky-600">Онлайн</p>
                  )}
                </div>
                <ChevronDown
                  size={20}
                  className={`text-gray-700 transition-transform flex-shrink-0 ${isProfileExpanded ? "rotate-180" : ""}`}
                />
              </button>
              {isProfileExpanded && (
                <div className="border-t border-sky-200 p-2 space-y-2">
                  <button
                    className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-white text-gray-700"
                    onClick={() => { setIsMobileLeftNavOpen(false); router.push('/profile'); }}
                  >Мой профиль</button>
                  <button
                    className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-white text-gray-700"
                    onClick={() => { setIsMobileLeftNavOpen(false); router.push('/settings'); }}
                  >Настройки</button>
                  <button
                    className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-red-50 text-red-600"
                    onClick={() => { setIsMobileLeftNavOpen(false); logout(); }}
                  >Выйти</button>
                </div>
              )}
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
            className={`absolute inset-y-0 right-0 w-full overflow-y-auto bg-white p-4 transition-transform duration-300 ${isMobileCalendarOpen ? "translate-x-0" : "translate-x-full"
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
            {isMobileCalendarOpen && (
              <CalendarCard
                onOpenCalendarModal={handleOpenCalendarModal}
                onOpenEventModal={handleOpenEventModal}
                onOpenParticipantsModal={handleOpenParticipantsModal}
                eventsRefreshTrigger={eventsRefreshTrigger}
                setEventsRefreshTrigger={handleSetEventsRefreshTrigger}
                setSidebarEvents={handleSetSidebarEvents}
                onCalendarChange={handleCalendarChange}
              />
            )}
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

        {/* Модальное окно участников календаря */}
        {participantsCalendar && (
          <CalendarParticipantsModal
            isOpen={showParticipantsModal}
            onClose={() => {
              setShowParticipantsModal(false);
              setParticipantsCalendar(null);
            }}
            calendarId={participantsCalendar.id}
            calendarName={participantsCalendar.name}
            userRole={participantsCalendar.user_role}
          />
        )}

        {/* Модальное окно события */}
        <EventModal
          isOpen={showEventModal}
          onClose={() => {
            setShowEventModal(false);
            setEditingEvent(null);
          }}
          event={editingEvent}
          onSave={handleEventSaved}
          showParticipants={true}
        />

        {/* Модальное окно просмотра событий дня */}
        <ViewDayEventsModal
          isOpen={showDayEventsModal}
          onClose={() => {
            setShowDayEventsModal(false);
            setSelectedDateForModal(null);
          }}
          date={selectedDateForModal}
          events={sidebarEvents}
          onEventClick={handleEventClickFromDay}
          onCreateEvent={handleCreateEventFromDay}
        />

        {/* Модальное окно просмотра деталей события */}
        <ViewEventDetailsModal
          isOpen={showEventDetailsModal}
          onClose={() => {
            setShowEventDetailsModal(false);
            setViewingEvent(null);
          }}
          event={viewingEvent}
          onEdit={handleEditFromDetails}
          onDelete={async () => {
            if (!viewingEvent?.id) return;
            if (!confirm("Удалить это событие?")) return;
            
            try {
              await apiClient.deleteEvent(viewingEvent.id);
              setShowEventDetailsModal(false);
              setViewingEvent(null);
              handleEventSaved(); // Обновляем список событий
            } catch (err) {
              console.error("Ошибка удаления события:", err);
              alert("Не удалось удалить событие");
            }
          }}
          showParticipants={true}
        />
      </div>
  );
}
