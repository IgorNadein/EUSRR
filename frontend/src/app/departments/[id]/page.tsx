"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "../../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { Department } from "@/types/api";
import { ArrowLeft, Building2, Users } from "lucide-react";

export default function DepartmentDetailPage() {
  const params = useParams<{ id: string }>();
  const departmentId = Number(params?.id);

  const [department, setDepartment] = useState<Department | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDepartment() {
      if (!departmentId || Number.isNaN(departmentId)) {
        setError("Некорректный идентификатор отдела");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getDepartment(departmentId);
        setDepartment(response);
      } catch (e) {
        console.error("Ошибка загрузки отдела:", e);
        setError("Не удалось загрузить отдел");
      } finally {
        setLoading(false);
      }
    }

    loadDepartment();
  }, [departmentId]);

  return (
    <AppShell>
      <div className="space-y-4">
        <Link
          href="/departments"
          className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
        >
          <ArrowLeft size={14} />
          К списку отделов
        </Link>

        {loading ? (
          <div className="app-surface rounded-2xl p-8 text-center">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка отдела...</p>
          </div>
        ) : error ? (
          <div className="app-feedback-danger rounded-2xl p-6 text-center">
            <p className="text-sm">{error}</p>
          </div>
        ) : department ? (
          <section className="app-surface rounded-2xl p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="app-selected app-accent-text mb-2 inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs">
                  <Building2 size={12} />
                  Отдел
                </div>
                <h1 className="text-xl font-semibold text-[var(--foreground)]">{department.name}</h1>
                <p className="app-text-muted mt-2 text-sm">{department.description || "Описание не заполнено"}</p>
                <p className="mt-3 text-sm text-[var(--foreground)]">
                  Руководитель:{" "}
                  <span className="font-medium">
                    {department.head
                      ? `${department.head.last_name} ${department.head.first_name}`.trim()
                      : "Не назначен"}
                  </span>
                </p>
              </div>

              <div className="app-selected app-accent-text inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs">
                <Users size={12} />
                {department.employees_count ?? 0}
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
