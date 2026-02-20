"use client";

import {
  Bell,
  Building2,
  CalendarDays,
  FileSignature,
  FileText,
  Home as HomeIcon,
  LogOut,
  Menu,
  MessageSquare,
  Search,
  Users,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useRef, useState } from "react";
import { useUser } from "@/contexts/UserContext";

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
  { href: "/employees", label: "Сотрудники", icon: Users },
  { href: "/departments", label: "Отделы", icon: Building2 },
  { href: "/requests", label: "Заявления", icon: FileSignature },
  { href: "/documents", label: "Документы", icon: FileText },
  { href: "/finances", label: "Финансы", icon: Wallet },
];

const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const calendarWeeks = [
  ["", "", "", "", "1", "2", "3"],
  ["4", "5", "6", "7", "8", "9", "10"],
  ["11", "12", "13", "14", "15", "16", "17"],
  ["18", "19", "20", "21", "22", "23", "24"],
  ["25", "26", "27", "28", "", "", ""],
];

function Header({ onOpenLeftNav, onOpenCalendar }: HeaderProps) {
  const router = useRouter();
  const { user, logout } = useUser();

  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isDesktopProfileMenuOpen, setIsDesktopProfileMenuOpen] = useState(false);
  const [isMobileProfileMenuOpen, setIsMobileProfileMenuOpen] = useState(false);

  const notificationsRef = useRef<HTMLDivElement>(null);
  const desktopProfileRef = useRef<HTMLDivElement>(null);
  const mobileProfileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;

      const clickedOutsideNotifications = notificationsRef.current && !notificationsRef.current.contains(target);
      const clickedOutsideDesktopProfile = desktopProfileRef.current && !desktopProfileRef.current.contains(target);
      const clickedOutsideMobileProfile = mobileProfileRef.current && !mobileProfileRef.current.contains(target);

      if (clickedOutsideNotifications) {
        setIsNotificationsOpen(false);
      }

      if (clickedOutsideDesktopProfile) {
        setIsDesktopProfileMenuOpen(false);
      }

      if (clickedOutsideMobileProfile) {
        setIsMobileProfileMenuOpen(false);
      }
    };

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsNotificationsOpen(false);
        setIsDesktopProfileMenuOpen(false);
        setIsMobileProfileMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEscape);

    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, []);

  const handleLogout = () => {
    setIsNotificationsOpen(false);
    setIsDesktopProfileMenuOpen(false);
    setIsMobileProfileMenuOpen(false);
    logout();
    router.push("/login");
  };

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  return (
    <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/95 backdrop-blur">
      <div className="mx-auto max-w-6xl px-4 sm:px-8">
        <div className="hidden h-14 items-center gap-4 lg:flex">
          <Link href="/" className="flex items-center gap-2">
            <img src="/logo.png" alt="Логотип" className="h-11 w-auto" />
          </Link>

          <div className="flex flex-1 items-center justify-center">
            <div className="relative w-full max-w-xl">
              <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-11 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="Поиск"
              />
            </div>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <div ref={notificationsRef} className="relative">
              <button
                type="button"
                onClick={() => {
                  setIsNotificationsOpen((prev) => !prev);
                  setIsDesktopProfileMenuOpen(false);
                }}
                className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
                aria-haspopup="menu"
                aria-expanded={isNotificationsOpen}
                aria-label="Открыть уведомления"
              >
                <Bell size={18} className="text-gray-600" />
              </button>

              {isNotificationsOpen ? (
                <div className="absolute right-0 top-12 z-40 w-56 rounded-xl bg-white p-3 text-sm text-gray-700 shadow-lg ring-1 ring-gray-100">
                  новых уведомлений нет
                </div>
              ) : null}
            </div>

            <div ref={desktopProfileRef} className="relative">
              <button
                type="button"
                onClick={() => {
                  setIsDesktopProfileMenuOpen((prev) => !prev);
                  setIsNotificationsOpen(false);
                }}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white overflow-hidden"
                aria-haspopup="menu"
                aria-expanded={isDesktopProfileMenuOpen}
                aria-label="Открыть меню профиля"
              >
                {user?.avatar ? (
                  <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                ) : (
                  userInitials
                )}
              </button>

              {isDesktopProfileMenuOpen ? (
                <div className="absolute right-0 top-12 z-40 w-44 rounded-xl bg-white p-2 shadow-lg ring-1 ring-gray-100">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    <LogOut size={16} />
                    Выйти
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="h-14 lg:hidden">
          <div className="relative flex h-full items-center justify-between">
            <button
              type="button"
              onClick={onOpenLeftNav}
              className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
              aria-label="Открыть левое меню"
            >
              <Menu size={20} className="text-gray-700" />
            </button>

            <Link href="/" className="absolute left-1/2 -translate-x-1/2">
              <img src="/logo.png" alt="Логотип" className="h-10 w-auto" />
            </Link>

            <button
              type="button"
              onClick={onOpenCalendar}
              className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100"
              aria-label="Открыть календарь"
            >
              <CalendarDays size={20} className="text-gray-700" />
            </button>
          </div>
        </div>

        <div className="pb-3 lg:hidden">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-10 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                placeholder="Поиск"
              />
            </div>

            <div ref={mobileProfileRef} className="relative">
              <button
                type="button"
                onClick={() => setIsMobileProfileMenuOpen((prev) => !prev)}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white overflow-hidden"
                aria-haspopup="menu"
                aria-expanded={isMobileProfileMenuOpen}
                aria-label="Открыть меню профиля"
              >
                {user?.avatar ? (
                  <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                ) : (
                  userInitials
                )}
              </button>

              {isMobileProfileMenuOpen ? (
                <div className="absolute right-0 top-12 z-40 w-44 rounded-xl bg-white p-2 shadow-lg ring-1 ring-gray-100">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    <LogOut size={16} />
                    Выйти
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

function LeftNavContent({ onNavigate }: LeftNavContentProps) {
  const pathname = usePathname();
  const { user } = useUser();

  const navLinkClass = (href: string) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50 ${
      pathname === href ? "bg-sky-50 text-sky-700 ring-1 ring-sky-100" : "text-gray-700"
    }`;

  const navIconClass = (href: string) => (pathname === href ? "text-sky-700" : "text-gray-400");

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white overflow-hidden">
          {user?.avatar ? (
            <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
          ) : (
            userInitials
          )}
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">{userName}</p>
          <p className="text-xs text-gray-500">{user?.is_active ? 'Онлайн' : 'Оффлайн'}</p>
        </div>
      </div>
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
    <aside className="hidden w-64 flex-shrink-0 lg:block">
      <div className="sticky top-8 space-y-4">
        <LeftNavContent />
      </div>
    </aside>
  );
}

function CalendarCard() {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
      <div className="flex items-center justify-between text-sm font-semibold text-gray-900">
        <span>Календарь</span>
        <span className="text-xs font-normal text-gray-500">Февраль 2026</span>
      </div>
      <div className="mt-4 grid grid-cols-7 gap-1 text-center text-xs text-gray-500">
        {weekdays.map((day) => (
          <div key={day} className="py-1 font-medium">
            {day}
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1 text-sm text-gray-800">
        {calendarWeeks.map((week, wi) =>
          week.map((day, di) => {
            const isToday = day === "18";
            return (
              <div
                key={`${wi}-${di}`}
                className={`flex h-9 items-center justify-center rounded-full ${
                  day
                    ? isToday
                      ? "bg-sky-100 text-sky-800 font-semibold ring-1 ring-sky-200"
                      : "hover:bg-sky-50"
                    : ""
                }`}
              >
                {day}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function Calendar() {
  return (
    <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block">
      <div className="sticky top-8 space-y-4">
        <CalendarCard />
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

  const [isMobileLeftNavOpen, setIsMobileLeftNavOpen] = useState(false);
  const [isMobileCalendarOpen, setIsMobileCalendarOpen] = useState(false);

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
    <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-white text-gray-900">
      <Header onOpenLeftNav={() => setIsMobileLeftNavOpen(true)} onOpenCalendar={() => setIsMobileCalendarOpen(true)} />
      <div className="mx-auto flex min-h-screen max-w-6xl gap-6 px-4 py-6 sm:px-8 lg:py-8">
        <LeftNav />
        <main className="flex-1 space-y-6">{children}</main>
        <Calendar />
      </div>

      {/* Мобильное левое меню */}
      <div className={`fixed inset-0 z-50 lg:hidden ${isMobileLeftNavOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
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

      {/* Мобильный календарь */}
      <div className={`fixed inset-0 z-50 lg:hidden ${isMobileCalendarOpen ? "pointer-events-auto" : "pointer-events-none"}`}>
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
          <CalendarCard />
        </div>
      </div>
    </div>
  );
}
