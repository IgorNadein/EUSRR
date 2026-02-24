"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { User } from "@/types/api";
import { Search, Users } from "lucide-react";

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
      } catch (e: any) {
        setError(String(e?.message || "Не удалось загрузить пользователей"));
      } finally {
        setLoading(false);
      }
    }

    loadUsers();
  }, []);

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...users].sort((a, b) => {
      const aName = `${a.last_name || ""} ${a.first_name || ""}`.trim().toLowerCase();
      const bName = `${b.last_name || ""} ${b.first_name || ""}`.trim().toLowerCase();
      return aName.localeCompare(bName, "ru");
    });

    if (!q) return sorted;

    return sorted.filter((u) => {
      const fullName = `${u.last_name || ""} ${u.first_name || ""} ${u.patronymic || ""}`.toLowerCase();
      const email = (u.email || "").toLowerCase();
      const phone = (u.phone_number || "").toLowerCase();
      const position = (u.position?.name || "").toLowerCase();
      return fullName.includes(q) || email.includes(q) || phone.includes(q) || position.includes(q);
    });
  }, [users, search]);

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка пользователей...</p>
        </div>
      ) : error ? (
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      ) : (
        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div className="relative mb-4">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск пользователя"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div className="space-y-2">
            {filteredUsers.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <Users size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Пользователи не найдены</p>
              </div>
            ) : (
              filteredUsers.map((u) => {
                const fullName = `${u.last_name || ""} ${u.first_name || ""} ${u.patronymic || ""}`.trim() || "Пользователь";
                const departmentsText = (u.departments || []).map((d) => d.name).filter(Boolean).join(", ");
                return (
                  <Link key={u.id} href={`/users/${u.id}`} className="block rounded-xl border border-gray-100 bg-white p-3 transition hover:bg-gray-50">
                    <p className="text-sm font-semibold text-gray-900">{fullName}</p>
                    <p className="mt-1 text-xs text-gray-500">{u.position?.name || "Сотрудник"}</p>
                    {departmentsText ? <p className="mt-1 text-xs text-gray-500">{departmentsText}</p> : null}
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
