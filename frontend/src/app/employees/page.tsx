"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { MessageCircle, Search } from "lucide-react";

import { AppShell } from "../../components/AppShell";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import type { Chat, User } from "@/types/api";

type PrivateChat = Chat & { member_ids?: number[] };

const getErrorMessage = (error: unknown, fallback: string) =>
  String((error as Error)?.message || fallback);

function getInitials(employee: User) {
  return `${employee.last_name?.[0] || ""}${employee.first_name?.[0] || ""}`;
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

  useEffect(() => {
    void loadEmployees(1, false);
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
                    <p className="app-text-wrap text-sm font-semibold text-[var(--foreground)]">
                      {fullName || "Сотрудник"}
                    </p>
                    <p className="app-text-muted text-xs">{position}</p>
                    {employee.email ? (
                      <p className="app-text-wrap app-text-muted mt-1 text-xs">
                        {employee.email}
                      </p>
                    ) : null}
                  </div>
                </Link>

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
