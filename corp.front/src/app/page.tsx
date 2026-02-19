"use client";

import { Bell, Bookmark, Building2, FileSignature, FileText, Heart, HeartHandshake, Home as HomeIcon, MessageSquare, Search, Star, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { usePosts, useCurrentUser } from "@/hooks/useApi";
import { useEffect } from "react";
import { apiClient } from "@/lib/api";

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInMs = now.getTime() - date.getTime();
  const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
  const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
  const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));

  if (diffInMinutes < 60) return `${diffInMinutes} минут назад`;
  if (diffInHours < 24) return `${diffInHours} часов назад`;
  return `${diffInDays} дней назад`;
}

const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const calendarWeeks = [
  ["", "", "", "", "1", "2", "3"],
  ["4", "5", "6", "7", "8", "9", "10"],
  ["11", "12", "13", "14", "15", "16", "17"],
  ["18", "19", "20", "21", "22", "23", "24"],
  ["25", "26", "27", "28", "", "", ""],
];

export default function Home() {
  const pathname = usePathname();
  const router = useRouter();
  const { posts, loading, error } = usePosts();
  const { user } = useCurrentUser();

  // Проверка авторизации при загрузке
  useEffect(() => {
    const token = apiClient.getToken();
    if (!token) {
      router.push('/login');
    }
  }, [router]);

  const navLinkClass = (href: string) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50 ${pathname === href ? "bg-sky-50 text-sky-700 ring-1 ring-sky-100" : "text-gray-700"
    }`;

  const navIconClass = (href: string) => (pathname === href ? "text-sky-700" : "text-gray-400");

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-white text-gray-900">
      <header className="sticky top-0 z-30 border-b border-slate-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-8">
          <div className="flex items-center gap-2">
            <img
              src="/logo.png"
              alt="Логотип"
              className="h-11 w-auto"
            />

          </div>
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
            <div className="ml-1 flex h-10 w-10 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">
              КМ
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto flex min-h-screen max-w-6xl gap-6 px-4 py-8 sm:px-8">
        <aside className="hidden w-64 flex-shrink-0 lg:block">
          <div className="sticky top-8 space-y-4">
            <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">
                  {user ? `${user.first_name[0]}${user.last_name[0]}` : 'ГК'}
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{user ? `${user.first_name} ${user.last_name}` : 'Гость'}</p>
                  <p className="text-xs text-gray-500">{user?.is_active ? 'Онлайн' : 'Оффлайн'}</p>
                </div>
              </div>
              <div className="space-y-2 text-sm text-gray-700">
                <Link href="/" className={navLinkClass("/")}>
                  <HomeIcon size={18} className={pathname === "/" ? "text-sky-700" : "text-sky-600"} />
                  Лента
                </Link>
                <Link href="/messages" className={navLinkClass("/messages")}>
                  <MessageSquare size={18} className={navIconClass("/messages")} />
                  Сообщения
                </Link>
                <Link href="/employees" className={navLinkClass("/employees")}>
                  <Users size={18} className={navIconClass("/employees")} />
                  Сотрудники
                </Link>
                <Link href="/departments" className={navLinkClass("/departments")}>
                  <Building2 size={18} className={navIconClass("/departments")} />
                  Отделы
                </Link>
                <Link href="/requests" className={navLinkClass("/requests")}>
                  <FileSignature size={18} className={navIconClass("/requests")} />
                  Заявления
                </Link>
                <Link href="/documents" className={navLinkClass("/documents")}>
                  <FileText size={18} className={navIconClass("/documents")} />
                  Документы
                </Link>
                <Link href="/finances" className={navLinkClass("/finances")}>
                  <Wallet size={18} className={navIconClass("/finances")} />
                  Финансы
                </Link>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex-1 space-y-6">
          <div className="flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-13 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">
                КМ
              </div>
              <div className="relative w-full">
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-10 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  placeholder="Поиск по ленте"
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-sky-700">
              <span className="rounded-full bg-sky-50 px-3 py-1">Статья</span>
              <span className="rounded-full bg-sky-50 px-3 py-1">Фото</span>
              <span className="rounded-full bg-sky-50 px-3 py-1">Ссылка</span>
              <span className="rounded-full bg-sky-50 px-3 py-1">Опрос</span>
              <span className="rounded-full bg-sky-50 px-3 py-1">Событие</span>
            </div>
          </div>

          <div className="space-y-4">
            {loading && (
              <div className="rounded-2xl bg-white p-10 text-center shadow-sm ring-1 ring-gray-100">
                <p className="text-gray-500">Загрузка...</p>
              </div>
            )}
            {error && (
              <div className="rounded-2xl bg-red-50 p-5 shadow-sm ring-1 ring-red-100">
                <p className="text-red-600">Ошибка загрузки: {error.message}</p>
                <p className="mt-2 text-sm text-red-500">Проверьте подключение к серверу</p>
              </div>
            )}
            {!loading && !error && posts.length === 0 && (
              <div className="rounded-2xl bg-white p-10 text-center shadow-sm ring-1 ring-gray-100">
                <p className="text-gray-500">Нет постов в ленте</p>
              </div>
            )}
            {!loading && posts.map((post) => (
              <article
                key={post.id}
                className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100"
              >
                <header className="mb-3 flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">
                      {post.author.first_name[0]}{post.author.last_name[0]}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{post.author.first_name} {post.author.last_name}</p>
                      <p className="text-xs text-gray-500">{formatTimeAgo(post.created_at)}</p>
                    </div>
                  </div>
                </header>
                <p className="text-sm leading-6 text-gray-800 whitespace-pre-wrap">{post.content}</p>
                {post.tags && post.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-sky-700">
                    {post.tags.map((tag) => (
                      <span key={tag} className="rounded-full bg-sky-50 px-3 py-1">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
                  <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                    <Heart size={16} className={post.is_liked ? "text-red-500 fill-red-500" : "text-gray-400"} /> {post.likes_count}
                  </button>
                  <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                    <MessageSquare size={16} className="text-gray-400" /> {post.comments_count}
                  </button>
                  <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                    <Bookmark size={16} className="text-gray-400" />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </main>

        <aside className="hidden w-72 flex-shrink-0 space-y-4 lg:block">
          <div className="sticky top-8 space-y-4">
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
      </div>
    </div>
  );
}
