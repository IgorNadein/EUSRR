"use client";

import Link from "next/link";
import { Search, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { User } from "@/types/api";

const getErrorMessage = (error: unknown, fallback: string) =>
  String((error as Error)?.message || fallback);

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadUsers() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getEmployees({ limit: 200 });
        setUsers(response.results || []);
      } catch (error: unknown) {
        setError(getErrorMessage(error, "Не удалось загрузить пользователей"));
      } finally {
        setLoading(false);
      }
    }

    void loadUsers();
  }, []);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    const sorted = [...users].sort((left, right) => {
      const leftName = `${left.last_name || ""} ${left.first_name || ""}`
        .trim()
        .toLowerCase();
      const rightName = `${right.last_name || ""} ${right.first_name || ""}`
        .trim()
        .toLowerCase();
      return leftName.localeCompare(rightName, "ru");
    });

    if (!query) return sorted;

    return sorted.filter((user) => {
      const fullName =
        `${user.last_name || ""} ${user.first_name || ""} ${user.patronymic || ""}`.toLowerCase();
      const email = (user.email || "").toLowerCase();
      const phone = (user.phone_number || "").toLowerCase();
      const position = (user.position?.name || "").toLowerCase();
      return (
        fullName.includes(query) ||
        email.includes(query) ||
        phone.includes(query) ||
        position.includes(query)
      );
    });
  }, [search, users]);

  return (
    <AppShell>
      {loading ? (
        <section className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка пользователей...</p>
        </section>
      ) : error ? (
        <section className="app-surface rounded-2xl p-6 text-center">
          <p className="text-sm text-red-400">{error}</p>
        </section>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          <div className="relative mb-4">
            <Search
              size={16}
              className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
            />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Поиск пользователя"
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            />
          </div>

          <div className="space-y-2">
            {filteredUsers.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-8 text-center">
                <Users size={22} className="app-text-muted mx-auto mb-2" />
                <p className="app-text-muted text-sm">Пользователи не найдены</p>
              </div>
            ) : (
              filteredUsers.map((user) => {
                const fullName =
                  `${user.last_name || ""} ${user.first_name || ""} ${user.patronymic || ""}`.trim() ||
                  "Пользователь";
                const departmentsText = (user.departments || [])
                  .map((department) => department.name)
                  .filter(Boolean)
                  .join(", ");

                return (
                  <Link
                    key={user.id}
                    href={`/users/${user.id}`}
                    className="app-surface-muted block rounded-xl p-3 transition hover:border-[var(--border-strong)] hover:bg-[var(--surface-elevated)]"
                  >
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      {fullName}
                    </p>
                    <p className="app-text-muted mt-1 text-xs">
                      {user.position?.name || "Сотрудник"}
                    </p>
                    {departmentsText ? (
                      <p className="app-text-muted mt-1 text-xs">
                        {departmentsText}
                      </p>
                    ) : null}
                  </Link>
                );
              })
            )}
          </div>
        </section>
      )}
    </AppShell>
  );
}
