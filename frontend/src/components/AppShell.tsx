"use client";

import { AlertTriangle, Building2, CalendarCheck, CalendarDays, Download, FileSignature, FileText, Home as HomeIcon, Kanban, Loader2, Menu, MessageSquare, ScrollText, Search, Send, ShoppingCart, UserRoundPlus, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ReactNode, Suspense, startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMobileNavPlacement } from "@/contexts/MobileNavPlacementContext";
import { useUser } from "@/contexts/UserContext";
import { useNotifications } from "@/hooks/useApi";
import { NotificationCenter, NotificationPanel } from "@/components/NotificationCenter";
import { CalendarSidebar } from "@/components/calendar/CalendarSidebar";
import { PushOnboardingPrompt } from "@/components/PushOnboardingPrompt";
import { useCalendarModals } from "@/hooks/useCalendarModals";
import { CalendarModals } from "@/components/layout/CalendarModals";
import { MobileLeftDrawer, MobileCalendarDrawer } from "@/components/layout/MobileDrawers";
import { usePwa } from "@/contexts/PwaContext";
import { Modal } from "@/components/ui";
import { apiClient } from "@/lib/api";
import { NAV_NOTIFICATION_CATEGORIES } from "@/lib/navigation-notifications";
import type { GuestVisit, GuestVisitComment } from "@/types/api";

type AppShellProps = {
  children: ReactNode;
  desktopWideMode?: boolean;
  onDesktopWideModeChange?: (enabled: boolean) => void;
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
  compact?: boolean;
  documentSection?: "folders" | "regulations";
};

type PaginatedResponse<T> = {
  count?: number;
  next?: string | null;
  results?: T[];
};

const navItems = [
  { href: "/", label: "Лента", icon: HomeIcon, category: NAV_NOTIFICATION_CATEGORIES.feed },
  { href: "/messages", label: "Сообщения", icon: MessageSquare, category: NAV_NOTIFICATION_CATEGORIES.messages },
  { href: "/employees", label: "Сотрудники", icon: Users },
  { href: "/departments", label: "Отделы", icon: Building2 },
  { href: "/attendance", label: "Посещаемость", icon: CalendarCheck },
  { href: "/requests", label: "Заявления", icon: FileSignature, category: NAV_NOTIFICATION_CATEGORIES.requests },
  { href: "/guests", label: "Гости", icon: UserRoundPlus, category: NAV_NOTIFICATION_CATEGORIES.guests },
  // { href: "/equipment", label: "Оборудование", icon: Monitor },
  { href: "/procurement", label: "Закупки", icon: ShoppingCart, category: NAV_NOTIFICATION_CATEGORIES.procurement, autoReadOnNavigate: false },
  { href: "/tasks", label: "Доска", icon: Kanban, category: NAV_NOTIFICATION_CATEGORIES.tasks },
  { href: "/documents?section=folders", label: "Документы", icon: FileText, category: NAV_NOTIFICATION_CATEGORIES.documents, documentSection: "folders" as const },
  { href: "/documents?section=regulations", label: "Регламенты", icon: ScrollText, category: NAV_NOTIFICATION_CATEGORIES.regulations, autoReadOnNavigate: false, documentSection: "regulations" as const },
  { href: "/finances", label: "Финансы", icon: Wallet },
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
                    className="app-menu-danger-item w-full px-4 py-2 text-left text-sm transition"
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

function LeftNavContent({ onNavigate, compact = false, documentSection = "folders" }: LeftNavContentProps) {
  const pathname = usePathname();
  const { user } = useUser();
  const { unreadCategoryCounts, markCategoryAsRead } = useNotifications();
  const canManageAttendance = Boolean(user?.auth?.is_staff || user?.auth?.is_superuser);
  const visibleNavItems = useMemo(
    () => navItems.filter((item) => item.href !== "/attendance" || canManageAttendance),
    [canManageAttendance],
  );

  const handleNavClick = async (category?: string, autoReadOnNavigate = true) => {
    // Помечаем уведомления категории как прочитанные
    if (autoReadOnNavigate && category && category !== "Сообщения" && (unreadCategoryCounts[category] || 0) > 0) {
      await markCategoryAsRead(category);
    }
    
    // Вызываем callback для закрытия мобильного меню
    if (onNavigate) {
      onNavigate();
    }
  };

  const isNavItemActive = (href: string, itemDocumentSection?: "folders" | "regulations") => {
    const hrefPath = href.split("?", 1)[0];
    if (hrefPath === "/documents" && itemDocumentSection) {
      const isDocumentsPath = pathname === "/documents" || pathname.startsWith("/documents/");
      return isDocumentsPath && documentSection === itemDocumentSection;
    }
    return pathname === hrefPath || (hrefPath !== "/" && pathname.startsWith(`${hrefPath}/`));
  };

  const navLinkClass = (href: string, itemDocumentSection?: "folders" | "regulations") =>
    `relative flex items-center rounded-lg transition ${compact ? "h-10 w-10 justify-center p-0" : "gap-3 px-3 py-2"} ${isNavItemActive(href, itemDocumentSection) ? "app-selected" : "text-[var(--foreground)] hover:bg-[var(--surface-secondary)]"
    }`;

  const navIconClass = (href: string, itemDocumentSection?: "folders" | "regulations") => (isNavItemActive(href, itemDocumentSection) ? "app-accent-text" : "app-text-muted");

  return (
    <div className={`app-surface rounded-2xl ${compact ? "p-2" : "p-5"}`}>
      <div className="space-y-2 text-sm">
        {visibleNavItems.map(({ href, label, icon: Icon, category, autoReadOnNavigate, documentSection: itemDocumentSection }) => {
          const count = category ? unreadCategoryCounts[category] || 0 : 0;
          
          return (
            <Link 
              key={href} 
              href={href} 
              className={navLinkClass(href, itemDocumentSection)}
              onClick={() => handleNavClick(category, autoReadOnNavigate)}
              title={compact ? label : undefined}
              aria-label={compact ? label : undefined}
            >
              <Icon size={18} className={navIconClass(href, itemDocumentSection)} />
              <span className={compact ? "sr-only" : "flex-1"}>{label}</span>
              {count > 0 && (
                <span className={`flex items-center justify-center rounded-full bg-sky-500 text-[10px] font-bold text-white ${compact ? "absolute -right-1 -top-1 h-4 min-w-4 px-1" : "h-5 min-w-[20px] px-1.5"}`}>
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

function SearchAwareLeftNavContent(props: Omit<LeftNavContentProps, "documentSection">) {
  const searchParams = useSearchParams();
  const documentSection = searchParams.get("section") === "regulations" ? "regulations" : "folders";
  return <LeftNavContent {...props} documentSection={documentSection} />;
}

function RoutedLeftNavContent(props: Omit<LeftNavContentProps, "documentSection">) {
  return (
    <Suspense fallback={<LeftNavContent {...props} />}>
      <SearchAwareLeftNavContent {...props} />
    </Suspense>
  );
}

function LeftNav({ fixedDesktop = false, compact = false }: { fixedDesktop?: boolean; compact?: boolean }) {
  return (
    <aside className={`hidden flex-shrink-0 transition-[width] duration-200 lg:block ${compact ? "w-14" : "w-64"}`}>
      <div
        className={`space-y-4 lg:overflow-y-auto ${
          fixedDesktop
            ? `lg:fixed lg:top-0 lg:bottom-0 lg:pt-[4.5rem] lg:pb-8 ${compact ? "lg:w-14" : "lg:w-64"}`
            : "lg:sticky lg:top-8 lg:max-h-[calc(100dvh-7.5rem)] lg:pb-2"
        }`}
      >
        <RoutedLeftNavContent compact={compact} />
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

const toResults = <T,>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) return payload;
  return payload.results || [];
};

const guestDisplayName = (visit: GuestVisit): string => (
  visit.guest.full_name
  || [visit.guest.last_name, visit.guest.first_name, visit.guest.patronymic].filter(Boolean).join(" ")
  || `Гость #${visit.guest.id}`
);

const latestInfoRequestText = (visit: GuestVisit, comments: GuestVisitComment[]): string => {
  const requestComment = [...comments]
    .reverse()
    .find((comment) => comment.metadata?.guest_visit_comment_type === "info_request");
  if (requestComment?.text) return requestComment.text;

  const requestEvent = [...(visit.events || [])]
    .reverse()
    .find((event) => event.event_type === "needs_info_requested" && event.comment);
  return requestEvent?.comment || "Администратор запросил дополнительную информацию по гостевой заявке.";
};

function GuestInfoRequestPrompt({ userId }: { userId?: number | null }) {
  const [visit, setVisit] = useState<GuestVisit | null>(null);
  const [comments, setComments] = useState<GuestVisitComment[]>([]);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPendingRequest = useCallback(async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const response = await apiClient.getGuestVisits({
        scope: "mine",
        status: "needs_info",
        ordering: "-updated_at",
        page: 1,
        limit: 1,
      }) as PaginatedResponse<GuestVisit> | GuestVisit[];
      const pendingVisit = toResults(response)[0] || null;
      setVisit(pendingVisit);
      if (!pendingVisit) {
        setComments([]);
        setAnswer("");
        return;
      }
      const commentResponse = await apiClient.getGuestVisitComments(pendingVisit.id) as GuestVisitComment[];
      setComments(commentResponse);
    } catch {
      setVisit(null);
      setComments([]);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (!userId) return;
    void loadPendingRequest();
    const interval = window.setInterval(() => void loadPendingRequest(), 30000);

    const handleFocus = () => void loadPendingRequest();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") void loadPendingRequest();
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [loadPendingRequest, userId]);

  const question = useMemo(
    () => visit ? latestInfoRequestText(visit, comments) : "",
    [comments, visit],
  );

  const submitAnswer = async () => {
    if (!visit || !answer.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      await apiClient.provideGuestVisitInfo(visit.id, { comment: answer.trim() });
      setAnswer("");
      await loadPendingRequest();
    } catch (err) {
      setError(String((err as Error)?.message || "Не удалось отправить ответ"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={Boolean(visit)}
      onClose={() => undefined}
      title="Требуется информация"
      size="md"
      showCloseButton={false}
      closeOnEsc={false}
      closeOnClickOutside={false}
      footer={
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => void submitAnswer()}
            disabled={submitting || !answer.trim()}
            className="app-action-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-60"
          >
            {submitting ? <Loader2 className="animate-spin" size={15} /> : <Send size={15} />}
            Отправить ответ
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="app-feedback-warning flex items-start gap-3 rounded-xl p-4 text-sm">
          <AlertTriangle className="mt-0.5 shrink-0" size={18} />
          <div className="min-w-0">
            <p className="font-semibold text-[var(--foreground)]">{visit ? guestDisplayName(visit) : "Гостевая заявка"}</p>
            <p className="mt-1 whitespace-pre-wrap">{loading ? "Загружаем запрос..." : question}</p>
          </div>
        </div>
        <label className="block">
          <span className="app-text-muted mb-1 block text-xs font-medium">Ответ *</span>
          <textarea
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
            rows={5}
            className="app-input w-full resize-none rounded-lg p-3 text-sm"
            placeholder="Напишите уточнение для администратора"
          />
        </label>
        {error ? <p className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{error}</p> : null}
      </div>
    </Modal>
  );
}

export function AppShell({ children, desktopWideMode = false, onDesktopWideModeChange }: AppShellProps) {
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
    <div className={`${isMessageDialogPage ? 'h-[100dvh] overflow-hidden lg:pt-14' : 'min-h-screen pt-10 lg:pt-14'} ${desktopWideMode ? "lg:h-[100dvh] lg:overflow-hidden" : ""} app-shell flex flex-col ${mobileNavPlacement === "bottom" && !isMessageDialogPage ? "pb-[calc(env(safe-area-inset-bottom)+3.75rem)] lg:pb-0" : ""}`}>
        <Header
          mobileNavPlacement={mobileNavPlacement}
          suppressMobileChrome={isMessageDialogPage}
          onOpenLeftNav={() => setIsMobileLeftNavOpen(true)}
          onOpenCalendar={() => setIsMobileCalendarOpen(true)}
        />
        <div className={`mx-auto flex w-full flex-1 min-h-0 max-w-6xl ${desktopWideMode ? "lg:max-w-none" : ""} ${isMessageDialogPage ? 'gap-0 px-0 py-0 lg:gap-6 lg:px-8 lg:py-4' : `gap-6 px-4 py-4 sm:px-8 lg:py-4 ${desktopWideMode ? "lg:gap-3 lg:px-3" : ""}`}`}>
          <LeftNav fixedDesktop compact={desktopWideMode} />
          <main className={`flex-1 min-w-0 min-h-0 space-y-6 ${isMessageDialogPage ? 'overflow-visible' : ''} ${desktopWideMode ? "lg:flex lg:flex-col lg:gap-4 lg:space-y-0 lg:overflow-hidden" : ""}`}>
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
            compact={desktopWideMode}
            onExpand={() => onDesktopWideModeChange?.(false)}
          />
        </div>

        <MobileLeftDrawer
          isOpen={isMobileLeftNavOpen}
          onClose={() => setIsMobileLeftNavOpen(false)}
        >
          <RoutedLeftNavContent onNavigate={() => setIsMobileLeftNavOpen(false)} />
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
        <GuestInfoRequestPrompt userId={user.id} />
      </div>
  );
}
