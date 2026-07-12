"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from "react";
import {
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  Clock3,
  MessageCircle,
  Search,
  UserRound,
  Users,
} from "lucide-react";

import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import { getEmployeeActionTone } from "@/lib/users/userDetailUtils";
import type { Chat, EmployeeStats, User } from "@/types/api";

type PrivateChat = Chat & { member_ids?: number[] };

const getErrorMessage = (error: unknown, fallback: string) =>
  String((error as Error)?.message || fallback);

function getInitials(employee: User) {
  return `${employee.last_name?.[0] || ""}${employee.first_name?.[0] || ""}`;
}

function pluralRu(value: number, one: string, few: string, many: string) {
  const normalized = Math.abs(Math.trunc(value));
  const mod10 = normalized % 10;
  const mod100 = normalized % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function formatAgeYears(value?: number | null) {
  if (value === null || value === undefined) return "—";
  const rounded = Number.isInteger(value) ? value : Number(value.toFixed(1));
  const suffix = Number.isInteger(rounded)
    ? pluralRu(rounded, "год", "года", "лет")
    : "года";
  return `${rounded.toLocaleString("ru-RU")} ${suffix}`;
}

function formatDurationDays(days?: number | null) {
  if (days === null || days === undefined) return "—";
  if (days < 30) {
    return `${days} ${pluralRu(days, "день", "дня", "дней")}`;
  }

  const years = Math.floor(days / 365);
  const months = Math.floor((days % 365) / 30);
  const parts: string[] = [];
  if (years) parts.push(`${years} ${pluralRu(years, "год", "года", "лет")}`);
  if (months) parts.push(`${months} ${pluralRu(months, "месяц", "месяца", "месяцев")}`);
  return parts.join(" ") || "меньше месяца";
}

function formatStatsDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function EmployeeStatsRow({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="flex items-start gap-3 px-2 py-2.5">
      <span className="app-badge mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <p className="app-card-caption min-w-0">{label}</p>
          <p className="max-w-[52%] truncate text-right text-sm font-semibold text-[var(--foreground)]">
            {value}
          </p>
        </div>
        {detail ? (
          <p className="app-text-wrap app-text-muted mt-1 text-xs">{detail}</p>
        ) : null}
      </div>
    </div>
  );
}

function EmployeeStatsSummary({
  error,
  loading,
  stats,
}: {
  error: string | null;
  loading: boolean;
  stats: EmployeeStats | null;
}) {
  const [open, setOpen] = useState(false);

  if (loading && !stats) {
    return (
      <div className="app-surface-muted mb-4 rounded-xl border border-[var(--border-subtle)] px-3 py-2.5">
        <p className="app-card-caption">Сотрудники</p>
        <p className="app-text-muted mt-1 text-sm">Загружаем счетчик...</p>
      </div>
    );
  }

  if (!stats) {
    return error ? (
      <div className="mb-4 app-feedback-warning rounded-xl px-4 py-3 text-sm">
        {error}
      </div>
    ) : null;
  }

  const youngest = stats.youngest_employee;
  const experienced = stats.most_experienced_employee;

  return (
    <div className="relative mb-4">
      <div className="app-surface-muted flex items-center justify-between gap-3 rounded-xl border border-[var(--border-subtle)] px-3 py-2.5">
        <div>
          <p className="app-card-caption">Сотрудники</p>
          <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
            <h1 className="text-2xl font-semibold leading-none text-[var(--foreground)]">
              {stats.total.toLocaleString("ru-RU")}
            </h1>
            <span className="app-text-muted text-xs">
              {pluralRu(stats.total, "сотрудник", "сотрудника", "сотрудников")}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          className="app-action-secondary inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium"
          aria-expanded={open}
        >
          Статистика
          <ChevronRight
            size={14}
            className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`}
          />
        </button>
      </div>

      {open ? (
        <div className="app-menu absolute right-0 top-full z-30 mt-2 w-full rounded-xl p-2 shadow-[var(--shadow-elevated)] sm:w-[26rem]">
          <EmployeeStatsRow
            icon={<UserRound size={16} />}
            label="Мужчины / женщины"
            value={`${stats.male_count.toLocaleString("ru-RU")} / ${stats.female_count.toLocaleString("ru-RU")}`}
            detail={`Пол не указан: ${stats.unknown_gender_count.toLocaleString("ru-RU")}`}
          />
          <div className="border-t border-[var(--border-subtle)]" />
          <EmployeeStatsRow
            icon={<CalendarDays size={16} />}
            label="Средний возраст"
            value={formatAgeYears(stats.average_age_years)}
            detail={`Расчет на ${formatStatsDate(stats.as_of)}`}
          />
          <div className="border-t border-[var(--border-subtle)]" />
          <EmployeeStatsRow
            icon={<UserRound size={16} />}
            label="Самый молодой"
            value={youngest?.full_name || "—"}
            detail={youngest ? formatAgeYears(youngest.age_years) : undefined}
          />
          <div className="border-t border-[var(--border-subtle)]" />
          <EmployeeStatsRow
            icon={<BriefcaseBusiness size={16} />}
            label="Самый опытный"
            value={experienced?.full_name || "—"}
            detail={experienced ? formatDurationDays(experienced.tenure_days) : undefined}
          />
          <div className="border-t border-[var(--border-subtle)]" />
          <EmployeeStatsRow
            icon={<Clock3 size={16} />}
            label="Самый долгий срок работы"
            value={formatDurationDays(stats.longest_tenure_days)}
            detail={experienced?.full_name}
          />
          <div className="border-t border-[var(--border-subtle)]" />
          <EmployeeStatsRow
            icon={<Users size={16} />}
            label="Средний срок работы"
            value={formatDurationDays(stats.average_tenure_days)}
            detail="По кадровым событиям"
          />
        </div>
      ) : null}
    </div>
  );
}

export default function EmployeesPage() {
  const router = useRouter();
  const { user: currentUser } = useUser();
  const [employees, setEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [creatingChatFor, setCreatingChatFor] = useState<number | null>(null);
  const [stats, setStats] = useState<EmployeeStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const loaderRef = useRef<HTMLDivElement | null>(null);
  const isFetchingRef = useRef(false);

  async function loadEmployees(pageToLoad: number, append: boolean) {
    if (isFetchingRef.current) return;

    try {
      isFetchingRef.current = true;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await apiClient.getEmployees({
        page: pageToLoad,
        limit: 20,
        is_active: true,
      });
      const nextChunk = response.results || [];

      setEmployees((current) =>
        append ? [...current, ...nextChunk] : nextChunk,
      );
      setHasMore(Boolean(response.next));
      setPage(pageToLoad);
    } catch (error: unknown) {
      console.error("Ошибка загрузки сотрудников:", error);
      setError(getErrorMessage(error, "Не удалось загрузить список сотрудников"));
    } finally {
      isFetchingRef.current = false;
      setLoading(false);
      setLoadingMore(false);
    }
  }

  async function loadEmployeeStats() {
    try {
      setStatsLoading(true);
      setStatsError(null);
      const response = await apiClient.getEmployeeStats();
      setStats(response as EmployeeStats);
    } catch (error: unknown) {
      console.error("Ошибка загрузки статистики сотрудников:", error);
      setStatsError(getErrorMessage(error, "Не удалось загрузить статистику сотрудников"));
    } finally {
      setStatsLoading(false);
    }
  }

  useEffect(() => {
    void loadEmployees(1, false);
    void loadEmployeeStats();
  }, []);

  async function handleStartChat(employee: User, event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (!currentUser || creatingChatFor === employee.id || currentUser.id === employee.id) {
      return;
    }

    setCreatingChatFor(employee.id);
    try {
      const allChats = (await apiClient.getAllChats()) as PrivateChat[];

      const existingChat = allChats.find((chat) => {
        if (chat.type !== "private") return false;

        const memberIds = Array.isArray(chat.member_ids) ? chat.member_ids : [];
        return (
          memberIds.length === 2 &&
          memberIds.includes(currentUser.id) &&
          memberIds.includes(employee.id)
        );
      });

      if (existingChat) {
        router.push(`/messages/${existingChat.id}`);
        return;
      }

      const chat = await apiClient.createChat({
        type: "private",
        name: "Диалог",
        participants: [employee.id],
      });
      router.push(`/messages/${chat.id}`);
    } catch (error: unknown) {
      console.error("Ошибка создания чата:", error);
      alert("Не удалось открыть чат");
    } finally {
      setCreatingChatFor(null);
    }
  }

  useEffect(() => {
    if (!hasMore || loading) return;

    const target = loaderRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (!first?.isIntersecting) return;
        if (isFetchingRef.current || loadingMore || !hasMore) return;
        void loadEmployees(page + 1, true);
      },
      {
        root: null,
        rootMargin: "300px 0px",
        threshold: 0.1,
      },
    );

    observer.observe(target);

    return () => {
      observer.disconnect();
    };
  }, [hasMore, loading, loadingMore, page]);

  const filteredEmployees = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return employees;

    return employees.filter((employee) => {
      const fullName =
        `${employee.last_name || ""} ${employee.first_name || ""} ${employee.patronymic || ""}`.trim().toLowerCase();
      const position = (employee.position?.name || "").toLowerCase();
      const email = (employee.email || "").toLowerCase();
      return fullName.includes(query) || position.includes(query) || email.includes(query);
    });
  }, [employees, search]);

  if (loading) {
    return (
      <AppShell>
        <section className="app-surface rounded-2xl p-8 text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка сотрудников...</p>
        </section>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <section className="app-surface rounded-2xl p-6 text-center">
          <p className="text-sm text-red-400">{error}</p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <section className="app-surface rounded-2xl p-4">
        <EmployeeStatsSummary
          error={statsError}
          loading={statsLoading}
          stats={stats}
        />

        <div className="relative mb-4">
          <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по сотрудникам"
            className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>

        <div className="space-y-3">
          {filteredEmployees.map((employee) => {
            const fullName =
              `${employee.last_name || ""} ${employee.first_name || ""} ${employee.patronymic || ""}`.trim();
            const initials = getInitials(employee);
            const position = employee.position?.name || "Сотрудник";
            const isCurrentUser = currentUser?.id === employee.id;
            const personnelState = employee.personnel_state;

            return (
              <div
                key={employee.id}
                className="app-surface-muted flex items-center gap-4 rounded-xl p-3 transition hover:border-[var(--border-strong)] hover:bg-[var(--surface-elevated)]"
              >
                <Link
                  href={`/users/${employee.id}`}
                  className="flex min-w-0 flex-1 items-center gap-4"
                >
                  <div
                    className={`${employee.avatar ? "app-avatar-frame" : "app-avatar-fallback"} flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full text-sm font-semibold`}
                  >
                    {employee.avatar ? (
                      <Image
                        src={resolveMediaUrl(employee.avatar)}
                        alt={fullName || "Сотрудник"}
                        width={48}
                        height={48}
                        className="h-full w-full object-cover"
                        unoptimized
                      />
                    ) : (
                      initials
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <p className="app-text-wrap min-w-0 text-sm font-semibold text-[var(--foreground)]">
                        {fullName || "Сотрудник"}
                      </p>
                      {personnelState ? (
                        <span
                          className={`app-status-pill shrink-0 ${getEmployeeActionTone(personnelState.status).badgeClass}`}
                        >
                          {personnelState.label || personnelState.status}
                        </span>
                      ) : null}
                    </div>
                    <p className="app-text-muted text-xs">{position}</p>
                    {employee.email ? (
                      <p className="app-text-wrap app-text-muted mt-1 text-xs">
                        {employee.email}
                      </p>
                    ) : null}
                  </div>
                </Link>

                <div className="flex shrink-0 items-center gap-2">
                  {!isCurrentUser ? (
                  <button
                    type="button"
                    onClick={(event) => void handleStartChat(employee, event)}
                    disabled={creatingChatFor === employee.id}
                    className="app-icon-button flex h-10 w-10 shrink-0 items-center justify-center rounded-full disabled:opacity-50"
                    title="Написать сообщение"
                  >
                    {creatingChatFor === employee.id ? (
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--accent-primary)] border-t-transparent" />
                    ) : (
                      <MessageCircle size={18} />
                    )}
                  </button>
                  ) : null}
                </div>
              </div>
            );
          })}

          {filteredEmployees.length === 0 ? (
            <div className="app-surface-muted rounded-xl p-8 text-center">
              <p className="app-text-muted text-sm">Сотрудники не найдены</p>
            </div>
          ) : null}

          <div ref={loaderRef} className="py-2">
            {loadingMore ? (
              <p className="app-text-muted text-center text-xs">
                Подгружаем сотрудников...
              </p>
            ) : !hasMore && employees.length > 0 ? (
              <p className="app-text-muted text-center text-xs">
                Все сотрудники загружены
              </p>
            ) : null}
          </div>
        </div>
      </section>
    </AppShell>
  );
}
