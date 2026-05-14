"use client";

import { Building2, CalendarCheck, CalendarDays, Download, FileSignature, FileText, Home as HomeIcon, Menu, MessageSquare, Monitor, Search, ShoppingCart, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, startTransition, useEffect, useRef, useState, useMemo } from "react";
import { useMobileNavPlacement } from "@/contexts/MobileNavPlacementContext";
import { useUser } from "@/contexts/UserContext";
import { useNotifications } from "@/hooks/useApi";
import { getVerbCategory } from "@/lib/verbTranslations";
import { NotificationCenter, NotificationPanel } from "@/components/NotificationCenter";
import { CalendarSidebar } from "@/components/calendar/CalendarSidebar";
import { PushOnboardingPrompt } from "@/components/PushOnboardingPrompt";
import { useCalendarModals } from "@/hooks/useCalendarModals";
import { CalendarModals } from "@/components/layout/CalendarModals";
import { MobileLeftDrawer, MobileCalendarDrawer } from "@/components/layout/MobileDrawers";
import { usePwa } from "@/contexts/PwaContext";

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
  mobileNavPlacement: "top" | "bottom";
  suppressMobileChrome?: boolean;
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
  { href: "/attendance", label: "Посещаемость", icon: CalendarCheck },
  { href: "/requests", label: "Заявления", icon: FileSignature, category: "Заявки" },
  // { href: "/equipment", label: "Оборудование", icon: Monitor },
  { href: "/procurement", label: "Закупки", icon: ShoppingCart, category: "Закупки" },
  { href: "/documents", label: "Документы", icon: FileText, category: "Документы" },
  // { href: "/finances", label: "Финансы", icon: Wallet },
];

function Header({ mobileNavPlacement, suppressMobileChrome = false, onOpenLeftNav, onOpenCalendar }: HeaderProps) {
  const router = useRouter();
  const { user, logout } = useUser();
  const { canInstall, install } = usePwa();
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

  // Закрытие панели уведомлений при клике вне
  useEffect(() => {
    if (!isNotificationsOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const notificationButton = document.querySelector('[aria-label="Уведомления"]');
      const notificationPanel = document.querySelector('.notification-panel-mobile');
      
      const insideButton = notificationButton && notificationButton.contains(target);
      const insidePanel = notificationPanel && notificationPanel.contains(target);
      
      if (!insideButton && !insidePanel) {
        setIsNotificationsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isNotificationsOpen]);

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  const isBottomMobileNav = mobileNavPlacement === "bottom";

  const submitSearch = () => {
    const query = searchQuery.trim();
    if (!query) return;
    router.push(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <header
      className={`app-header z-[40] backdrop-blur ${
        isBottomMobileNav
          ? "fixed inset-x-0 bottom-0 border-t lg:fixed lg:inset-x-0 lg:top-0 lg:bottom-auto lg:border-b lg:border-t-0"
          : "fixed inset-x-0 top-0 border-b"
      } ${suppressMobileChrome ? "hidden lg:block" : ""} shrink-0`}
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-8">
        <div
          className={`flex h-10 items-center justify-between gap-3 lg:h-14 ${
            isBottomMobileNav ? "pb-[max(env(safe-area-inset-bottom),0px)]" : ""
          }`}
        >
          <button
            type="button"
            onClick={onOpenLeftNav}
            className="app-icon-button flex h-10 w-10 items-center justify-center rounded-full lg:hidden"
            aria-label="Открыть левое меню"
          >
            <Menu size={20} />
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
            className="app-icon-button flex h-10 w-10 items-center justify-center rounded-full lg:hidden"
            aria-label="Поиск"
          >
            <Search size={20} />
          </button>

          <Link href="/" className="flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt="Логотип"
              className={`h-10 w-auto rounded bg-transparent pb-0.5 lg:h-11 lg:pb-0 ${
                isBottomMobileNav ? "mt-0" : "mt-3 lg:mt-0"
              }`}
            />
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
            className="app-icon-button flex h-10 w-10 items-center justify-center rounded-full lg:hidden"
            aria-label="Открыть календарь"
          >
            <CalendarDays size={20} />
          </button>

          <div className="hidden flex-1 items-center justify-center lg:flex">
            <form
              className="relative w-full max-w-xl"
              onSubmit={(e) => {
                e.preventDefault();
                submitSearch();
              }}
            >
              <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 app-text-muted" />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                enterKeyHint="search"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    submitSearch();
                  }
                }}
                className="app-input w-full rounded-full py-2.5 pl-11 pr-4 text-sm"
                placeholder="Поиск"
              />
            </form>
          </div>

          <div className="ml-auto hidden items-center gap-1 sm:gap-2 lg:flex">
            <NotificationCenter />
            <div className="ml-1 relative h-10 w-10" id="user-menu-root">
              <div
                className="app-avatar-fallback flex h-10 w-10 cursor-pointer items-center justify-center overflow-hidden rounded-full text-sm font-semibold hover:bg-[var(--accent-soft-strong)]"
                title={userName}
                onClick={() => setUserMenuOpen((v) => !v)}
              >
                {user?.avatar ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                ) : (
                  userInitials
                )}
              </div>
              {/* Меню пользователя */}
              {userMenuOpen && (
                <div className="app-menu absolute right-0 top-12 z-[60] w-48 rounded-xl py-2 animate-fade-in">
                  <button
                    className="app-action-ghost w-full px-4 py-2 text-left text-sm transition"
                    onClick={() => { setUserMenuOpen(false); router.push('/profile'); }}
                  >Мой профиль</button>
                  <button
                    className="app-action-ghost w-full px-4 py-2 text-left text-sm transition"
                    onClick={() => { setUserMenuOpen(false); router.push('/settings'); }}
                  >Настройки</button>
                  {canInstall ? (
                    <button
                      className="app-action-ghost flex w-full items-center gap-2 px-4 py-2 text-left text-sm transition"
                      onClick={() => {
                        setUserMenuOpen(false);
                        void install();
                      }}
                    >
                      <Download size={16} />
                      Установить
                    </button>
                  ) : null}
                  <div className="app-divider my-1 border-t" />
                  <button
                    className="app-action-danger w-full px-4 py-2 text-left text-sm transition"
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
          } ${isBottomMobileNav ? "absolute inset-x-0 bottom-full px-4 sm:px-8" : ""}`}
        >
          <form
            className={`relative ${isBottomMobileNav ? "mx-auto max-w-6xl" : ""}`}
            onSubmit={(e) => {
              e.preventDefault();
              submitSearch();
              setIsSearchOpen(false);
            }}
          >
            <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 app-text-muted" />
            <input
              ref={searchInputRef}
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              enterKeyHint="search"
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
              className="app-input w-full rounded-full py-2.5 pl-11 pr-12 text-sm"
              placeholder="Поиск по сайту..."
            />
            <button
              type="submit"
              className="app-action-primary absolute right-1.5 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full"
              aria-label="Найти"
              title="Найти"
            >
              <Search size={14} />
            </button>
          </form>
        </div>

        {/* Мобильная панель уведомлений */}
        <div
          className={`notification-panel-mobile overflow-hidden transition-all duration-300 lg:hidden ${
            isNotificationsOpen ? "max-h-[70vh] pb-3" : "max-h-0"
          } ${isBottomMobileNav ? "absolute inset-x-0 bottom-full px-4 sm:px-8" : ""}`}
        >
          {isNotificationsOpen && (
            <div className={isBottomMobileNav ? "mx-auto max-w-6xl" : ""}>
              <NotificationPanel onClose={() => setIsNotificationsOpen(false)} />
            </div>
          )}
        </div>

      </div>
    </header>
  );
}

function LeftNavContent({ onNavigate }: LeftNavContentProps) {
  const pathname = usePathname();
  const { user } = useUser();
  const { notifications: notificationsData, markCategoryAsRead } = useNotifications();
  const notifications = useMemo(() => Array.isArray(notificationsData) ? notificationsData : [], [notificationsData]);
  const canManageAttendance = Boolean(user?.auth?.is_staff || user?.auth?.is_superuser);
  const visibleNavItems = useMemo(
    () => navItems.filter((item) => item.href !== "/attendance" || canManageAttendance),
    [canManageAttendance],
  );

  // Подсчет уведомлений по категориям
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    
    notifications.forEach((n: { verb?: string; is_read?: boolean }) => {
      // Пропускаем прочитанные
      if (!n.verb || n.is_read) return;
      const category = getVerbCategory(n.verb);
      counts[category] = (counts[category] || 0) + 1;
    });
    
    return counts;
  }, [notifications]);

  const handleNavClick = async (category?: string) => {
    // Помечаем уведомления категории как прочитанные
    if (category && category !== "Сообщения" && categoryCounts[category] > 0) {
      await markCategoryAsRead(category);
    }
    
    // Вызываем callback для закрытия мобильного меню
    if (onNavigate) {
      onNavigate();
    }
  };

  const navLinkClass = (href: string) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 transition ${pathname === href ? "app-selected" : "text-[var(--foreground)] hover:bg-[var(--surface-secondary)]"
    }`;

  const navIconClass = (href: string) => (pathname === href ? "app-accent-text" : "app-text-muted");

  return (
    <div className="app-surface rounded-2xl p-5">
      <div className="space-y-2 text-sm">
        {visibleNavItems.map(({ href, label, icon: Icon, category }) => {
          const count = category ? categoryCounts[category] || 0 : 0;
          
          return (
            <Link 
              key={href} 
              href={href} 
              className={navLinkClass(href)} 
              onClick={() => handleNavClick(category)}
            >
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

function LeftNav({ fixedDesktop = false }: { fixedDesktop?: boolean }) {
  return (
    <aside className="hidden w-64 flex-shrink-0 lg:block">
      <div
        className={`space-y-4 lg:overflow-y-auto ${
          fixedDesktop
            ? "lg:fixed lg:top-0 lg:bottom-0 lg:w-64 lg:pt-[4.5rem] lg:pb-8"
            : "lg:sticky lg:top-8 lg:max-h-[calc(100dvh-7.5rem)] lg:pb-2"
        }`}
      >
        <LeftNavContent />
      </div>
    </aside>
  );
}

export function PageHeader({ title, subtitle, badge, eyebrow  }: PageHeaderProps) {
  return (
    <div className="app-surface flex flex-col gap-3 rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="app-accent-text text-sm font-semibold">{eyebrow}</p>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">{title}</h1>
        </div>
        {badge ? (
          <div className="app-badge app-badge-accent px-4 py-2 text-xs font-medium">{badge}</div>
        ) : null}
      </div>
      {subtitle ? <p className="app-text-muted text-sm">{subtitle}</p> : null}
    </div>
  );
}

export function AppShell({ children }: AppShellProps) {
  const { user, loading } = useUser();
  const { mobileNavPlacement } = useMobileNavPlacement();
  const router = useRouter();
  const pathname = usePathname();
  const isMessageDialogPage = pathname.startsWith('/messages/') && 
    pathname !== '/messages' && 
    !pathname.includes('/settings');

  const [isMobileLeftNavOpen, setIsMobileLeftNavOpen] = useState(false);
  const [isMobileCalendarOpen, setIsMobileCalendarOpen] = useState(false);

  const prevPathnameRef = useRef(pathname);

  const cal = useCalendarModals();

  useEffect(() => {
    // Если загрузка завершена и пользователь не авторизован - редирект на логин
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  // Close mobile drawers on route change
  useEffect(() => {
    if (prevPathnameRef.current !== pathname) {
      prevPathnameRef.current = pathname;
      startTransition(() => {
        setIsMobileLeftNavOpen(false);
        setIsMobileCalendarOpen(false);
      });
    }
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
      <div className="app-shell min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-sky-400 border-t-transparent"></div>
          <p className="app-text-muted text-sm">Загрузка...</p>
        </div>
      </div>
    );
  }

  // Если пользователь не авторизован, ничего не показываем (уже редиректим)
  if (!user) {
    return null;
  }

  return (
    <div className={`${isMessageDialogPage ? 'h-[100dvh] overflow-hidden lg:pt-14' : 'min-h-screen pt-10 lg:pt-14'} app-shell flex flex-col ${mobileNavPlacement === "bottom" && !isMessageDialogPage ? "pb-[calc(env(safe-area-inset-bottom)+3.75rem)] lg:pb-0" : ""}`}>
        <Header
          mobileNavPlacement={mobileNavPlacement}
          suppressMobileChrome={isMessageDialogPage}
          onOpenLeftNav={() => setIsMobileLeftNavOpen(true)}
          onOpenCalendar={() => setIsMobileCalendarOpen(true)}
        />
        <div className={`mx-auto flex w-full flex-1 min-h-0 max-w-6xl ${isMessageDialogPage ? 'gap-0 px-0 py-0 lg:gap-6 lg:px-8 lg:py-4' : 'gap-6 px-4 py-4 sm:px-8 lg:py-4'}`}>
          <LeftNav fixedDesktop />
          <main className={`flex-1 min-w-0 min-h-0 space-y-6 ${isMessageDialogPage ? 'overflow-visible' : ''}`}>
            {!isMessageDialogPage ? <PushOnboardingPrompt /> : null}
            {children}
          </main>
          <CalendarSidebar
            onOpenCalendarModal={cal.handleOpenCalendarModal}
            onOpenEventModal={cal.handleOpenEventModal}
            onOpenParticipantsModal={cal.handleOpenParticipantsModal}
            eventsRefreshTrigger={cal.eventsRefreshTrigger}
            setEventsRefreshTrigger={cal.handleSetEventsRefreshTrigger}
            setSidebarEvents={cal.handleSetSidebarEvents}
            onCalendarChange={cal.handleCalendarChange}
            fixedDesktop
          />
        </div>

        <MobileLeftDrawer
          isOpen={isMobileLeftNavOpen}
          onClose={() => setIsMobileLeftNavOpen(false)}
        >
          <LeftNavContent onNavigate={() => setIsMobileLeftNavOpen(false)} />
        </MobileLeftDrawer>

        <MobileCalendarDrawer
          isOpen={isMobileCalendarOpen}
          onClose={() => setIsMobileCalendarOpen(false)}
          onOpenCalendarModal={cal.handleOpenCalendarModal}
          onOpenEventModal={cal.handleOpenEventModal}
          onOpenParticipantsModal={cal.handleOpenParticipantsModal}
          eventsRefreshTrigger={cal.eventsRefreshTrigger}
          setEventsRefreshTrigger={cal.handleSetEventsRefreshTrigger}
          setSidebarEvents={cal.handleSetSidebarEvents}
          onCalendarChange={cal.handleCalendarChange}
        />

        <CalendarModals {...cal} />
      </div>
  );
}
