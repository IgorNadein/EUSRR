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
          className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          <ArrowLeft size={14} />
          К списку отделов
        </Link>

        {loading ? (
          <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
            <p className="text-sm text-gray-500">Загрузка отдела...</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-red-50 p-6 text-center">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        ) : department ? (
          <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700 ring-1 ring-sky-100">
                  <Building2 size={12} />
                  Отдел
                </div>
                <h1 className="text-xl font-semibold text-gray-900">{department.name}</h1>
                <p className="mt-2 text-sm text-gray-600">{department.description || "Описание не заполнено"}</p>
                <p className="mt-3 text-sm text-gray-700">
                  Руководитель:{" "}
                  <span className="font-medium">
                    {department.head
                      ? `${department.head.last_name} ${department.head.first_name}`.trim()
                      : "Не назначен"}
                  </span>
                </p>
              </div>

              <div className="inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700 ring-1 ring-sky-100">
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
