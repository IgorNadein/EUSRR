"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { AppShell } from "../../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { User } from "@/types/api";

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || "").trim();

function resolveMediaUrl(url?: string | null): string {
  const raw = (url || "").trim();
  if (!raw) return "";
  if (raw.startsWith("data:")) return raw;
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return raw;

  if (BACKEND_URL) {
    const base = BACKEND_URL.replace(/\/$/, "");
    return `${base}/${raw.replace(/^\/+/, "")}`;
  }

  return `/${raw.replace(/^\/+/, "")}`;
}

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
        <Link href="/employees" className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
          ← К списку сотрудников
        </Link>

        {loading ? (
          <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
            <p className="text-sm text-gray-500">Загрузка профиля...</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-red-50 p-6 text-center">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        ) : employee ? (
          <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-lg font-semibold text-white">
                {employee.avatar ? (
                  <Image src={resolveMediaUrl(employee.avatar)} alt={fullName} width={64} height={64} className="h-full w-full object-cover" unoptimized />
                ) : (
                  <span>{`${employee.last_name?.[0] || ""}${employee.first_name?.[0] || ""}` || "С"}</span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <h1 className="truncate text-xl font-semibold text-gray-900">{fullName}</h1>
                <p className="mt-1 text-sm text-gray-600">Должность: {employee.position?.name || "—"}</p>
                <p className="mt-1 text-sm text-gray-600">Email: {employee.email || "—"}</p>
                <p className="mt-1 text-sm text-gray-600">Телефон: {employee.phone_number || "—"}</p>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
