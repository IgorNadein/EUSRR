"use client";

import { Bell, Building2, FileSignature, FileText, Home as HomeIcon, MessageSquare, Search, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
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

function Header() {
  const { user, logout } = useUser();

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  return (
    <header className="sticky top-0 z-30 border-b border-slate-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-8">
        <Link href="/" className="flex items-center gap-2">
          <img src="/logo.png" alt="Логотип" className="h-11 w-auto" />
        </Link>
        <div className="hidden flex-1 items-center justify-center md:flex">
          <div className="relative w-full max-w-xl">
            <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-11 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              placeholder="Поиск"
            />
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <button className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-slate-100">
            <Bell size={18} className="text-gray-600" />
          </button>
          <div
            className="ml-1 relative h-10 w-10 cursor-pointer"
            title={userName}
            onClick={() => {
              if (confirm('Выйти из системы?')) {
                logout();
              }
            }}
          >
            <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white hover:bg-sky-500">
              {user?.avatar ? (
                <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
              ) : (
                userInitials
              )}
            </div>
            {user?.is_active ? (
              <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}

function LeftNav() {
  const pathname = usePathname();
  const { user } = useUser();

  const userInitials = user
    ? `${user.last_name?.[0] || ''}${user.first_name?.[0] || ''}`
    : 'Г';
  const userName = user
    ? `${user.last_name} ${user.first_name}`.trim()
    : 'Гость';

  const navLinkClass = (href: string) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50 ${pathname === href ? "bg-sky-50 text-sky-700 ring-1 ring-sky-100" : "text-gray-700"
    }`;

  const navIconClass = (href: string) => (pathname === href ? "text-sky-700" : "text-gray-400");

  return (
    <aside className="hidden w-64 flex-shrink-0 lg:block lg:sticky lg:self-start lg:top-22 lg:max-h-[calc(100vh-5.5rem)] lg:overflow-y-auto">
      <div className="space-y-4">
        <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 flex items-center gap-3">
            <div className="relative h-11 w-11">
              <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                {user?.avatar ? (
                  <img src={user.avatar} alt={userName} className="h-full w-full object-cover" />
                ) : (
                  userInitials
                )}
              </div>
              {user?.is_active ? (
                <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
              ) : null}
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">{userName}</p>
              <p className="text-xs text-gray-500">{user?.is_active ? 'Онлайн' : 'Оффлайн'}</p>
            </div>
          </div>
          <div className="space-y-2 text-sm text-gray-700">
            {navItems.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} className={navLinkClass(href)}>
                <Icon size={18} className={navIconClass(href)} />
                {label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

function Calendar() {
  return (
    <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block lg:sticky lg:self-start lg:top-22 lg:max-h-[calc(100vh-5.5rem)] lg:overflow-y-auto">
      <div className="space-y-4">
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
                    className={`flex h-9 items-center justify-center rounded-full ${day
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

  useEffect(() => {
    // Если загрузка завершена и пользователь не авторизован - редирект на логин
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

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
      <Header />
      <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-6xl gap-6 px-4 py-8 sm:px-8">
        <LeftNav />
        <main className="flex-1 min-w-0 space-y-6">{children}</main>
        <Calendar />
      </div>
    </div>
  );
}
