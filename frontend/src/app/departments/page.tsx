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
        <div className="app-surface rounded-2xl p-8 text-center">
          <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
          <p className="app-text-muted text-sm">Загрузка отделов...</p>
        </div>
      ) : error ? (
        <div className="app-feedback-danger rounded-2xl p-6 text-center">
          <p className="text-sm">{error}</p>
        </div>
      ) : (
        <section className="app-surface rounded-2xl p-4">
          <div className="relative mb-4">
            <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по отделам"
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            />
          </div>

          <div className="space-y-3">
            {filteredDepartments.length === 0 ? (
              <div className="app-surface-muted rounded-xl p-8 text-center">
                <Building2 size={22} className="app-text-muted mx-auto mb-2" />
                <p className="app-text-muted text-sm">Отделы не найдены</p>
              </div>
            ) : (
              filteredDepartments.map((department) => {
                const headName = department.head
                  ? `${department.head.last_name} ${department.head.first_name}`.trim()
                  : "Не назначен";
                const directMembersCount = department.employees_count ?? 0;
                const roleOnlyCount = department.role_only_count ?? 0;

                return (
                  <Link key={department.id} href={`/departments/${department.id}`} className="app-surface-muted block rounded-xl p-4 transition hover:bg-[var(--surface-elevated)]">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[var(--foreground)]">{department.name}</p>
                        <p className="app-text-muted mt-1 text-xs">Руководитель: {headName}</p>
                        <p className="app-text-muted mt-2 text-sm">{department.description || "Описание не заполнено"}</p>
                      </div>
                      <div
                        className="app-selected app-accent-text inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
                        title="Участники отдела • Только роли без членства"
                      >
                        <Users size={12} />
                        <span>{directMembersCount}</span>
                        <span className="opacity-60">•</span>
                        <span>{roleOnlyCount}</span>
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
