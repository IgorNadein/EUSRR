"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { AppShell } from "../../../components/AppShell";
import { apiClient } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/url";
import type { User } from "@/types/api";

export default function EmployeeDetailPage() {
  const params = useParams<{ id: string }>();
  const employeeId = Number(params?.id);

  const [employee, setEmployee] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadEmployee() {
      if (!employeeId || Number.isNaN(employeeId)) {
        setError("Некорректный идентификатор сотрудника");
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getEmployee(employeeId);
        setEmployee(data);
      } catch (e: any) {
        setError(String(e?.message || "Не удалось загрузить профиль сотрудника"));
      } finally {
        setLoading(false);
      }
    }

    loadEmployee();
  }, [employeeId]);

  const fullName = useMemo(() => {
    if (!employee) return "";
    return `${employee.last_name || ""} ${employee.first_name || ""} ${employee.patronymic || ""}`.trim() || "Сотрудник";
  }, [employee]);

  return (
    <AppShell>
      <div className="space-y-4">
        <Link href="/employees" className="app-action-secondary inline-flex items-center rounded-lg px-3 py-2 text-sm">
          ← К списку сотрудников
        </Link>

        {loading ? (
          <div className="app-surface rounded-2xl p-8 text-center">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]" />
            <p className="app-text-muted text-sm">Загрузка профиля...</p>
          </div>
        ) : error ? (
          <div className="app-feedback-danger rounded-2xl p-6 text-center">
            <p className="text-sm">{error}</p>
          </div>
        ) : employee ? (
          <section className="app-surface rounded-2xl p-5">
            <div className="flex items-start gap-4">
              <div className="app-avatar-fallback flex h-16 w-16 items-center justify-center overflow-hidden rounded-full text-lg font-semibold">
                {employee.avatar ? (
                  <Image src={resolveMediaUrl(employee.avatar)} alt={fullName} width={64} height={64} className="h-full w-full object-cover" unoptimized />
                ) : (
                  <span>{`${employee.last_name?.[0] || ""}${employee.first_name?.[0] || ""}` || "С"}</span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <h1 className="truncate text-xl font-semibold text-[var(--foreground)]">{fullName}</h1>
                <p className="app-text-muted mt-1 text-sm">Должность: {employee.position?.name || "—"}</p>
                <p className="app-text-muted mt-1 text-sm">Email: {employee.email || "—"}</p>
                <p className="app-text-muted mt-1 text-sm">Телефон: {employee.phone_number || "—"}</p>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
