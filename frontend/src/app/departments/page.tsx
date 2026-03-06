"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Department } from "@/types/api";
import { Building2, Search, Users } from "lucide-react";

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDepartments() {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getDepartments();
        setDepartments(response.results || []);
      } catch (err) {
        console.error("Ошибка загрузки отделов:", err);
        setError("Не удалось загрузить отделы");
      } finally {
        setLoading(false);
      }
    }

    loadDepartments();
  }, []);

  const filteredDepartments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const sorted = [...departments].sort((a, b) => a.name.localeCompare(b.name, "ru"));
    if (!q) return sorted;

    return sorted.filter((dep) => {
      const name = dep.name.toLowerCase();
      const desc = (dep.description || "").toLowerCase();
      const head = dep.head ? `${dep.head.last_name} ${dep.head.first_name}`.toLowerCase() : "";
      return name.includes(q) || desc.includes(q) || head.includes(q);
    });
  }, [departments, search]);

  return (
    <AppShell>
      {loading ? (
        <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm text-gray-500">Загрузка отделов...</p>
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
              placeholder="Поиск по отделам"
              className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div className="space-y-3">
            {filteredDepartments.length === 0 ? (
              <div className="rounded-xl bg-gray-50 p-8 text-center">
                <Building2 size={22} className="mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">Отделы не найдены</p>
              </div>
            ) : (
              filteredDepartments.map((department) => {
                const headName = department.head
                  ? `${department.head.last_name} ${department.head.first_name}`.trim()
                  : "Не назначен";

                return (
                  <Link key={department.id} href={`/departments/${department.id}`} className="block rounded-xl border border-gray-100 bg-white p-4 transition hover:bg-gray-50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-gray-900">{department.name}</p>
                        <p className="mt-1 text-xs text-gray-500">Руководитель: {headName}</p>
                        <p className="mt-2 text-sm text-gray-600">{department.description || "Описание не заполнено"}</p>
                      </div>
                      <div className="inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700 ring-1 ring-sky-100">
                        <Users size={12} />
                        {department.employees_count ?? 0}
                      </div>
                    </div>
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
