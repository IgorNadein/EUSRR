"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useRef, useState } from "react";
import type { User } from "@/types/api";

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const loaderRef = useRef<HTMLDivElement | null>(null);
  const isFetchingRef = useRef(false);

  const loadEmployees = async (pageToLoad: number, append: boolean) => {
    if (isFetchingRef.current) return;

    try {
      isFetchingRef.current = true;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const response = await apiClient.getEmployees({ page: pageToLoad, limit: 20 });
      const nextChunk = response.results || [];

      setEmployees((prev) => (append ? [...prev, ...nextChunk] : nextChunk));
      setHasMore(Boolean(response.next));
      setPage(pageToLoad);
    } catch (err: any) {
      console.error("Ошибка загрузки сотрудников:", err);
      setError("Не удалось загрузить список сотрудников");
    } finally {
      isFetchingRef.current = false;
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadEmployees(1, false);
  }, []);

  useEffect(() => {
    if (!hasMore || loading) return;

    const target = loaderRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (!first?.isIntersecting) return;
        if (isFetchingRef.current || loadingMore || !hasMore) return;
        loadEmployees(page + 1, true);
      },
      {
        root: null,
        rootMargin: "300px 0px",
        threshold: 0.1,
      }
    );

    observer.observe(target);

    return () => {
      observer.disconnect();
    };
  }, [page, hasMore, loading, loadingMore]);

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent"></div>
            <p className="text-sm text-gray-500">Загрузка...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="rounded-2xl bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      </AppShell>
    );
  }

  const sortedEmployees = [...employees].sort((a, b) => {
    const nameA = `${a.last_name} ${a.first_name}`.trim();
    const nameB = `${b.last_name} ${b.first_name}`.trim();
    return nameA.localeCompare(nameB, "ru");
  });

  return (
    <AppShell>
      <div className="space-y-3">
        {sortedEmployees.map((employee) => {
          const fullName = `${employee.last_name} ${employee.first_name} ${employee.patronymic || ''}`.trim();
          const initials = `${employee.last_name?.[0] || ''}${employee.first_name?.[0] || ''}`;
          const position = employee.position?.name || 'Сотрудник';
          const isOnline = employee.is_active;
          const statusText = isOnline ? 'Активен' : 'Неактивен';
          const dotColor = isOnline ? 'bg-green-500' : 'bg-gray-400';
          const statusColor = isOnline ? 'text-green-600' : 'text-gray-500';

          return (
            <article key={employee.id} className="flex items-center gap-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
              <div className="relative h-12 w-12">
                <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                  {employee.avatar ? (
                    <img src={employee.avatar} alt={fullName} className="h-full w-full object-cover" />
                  ) : (
                    initials
                  )}
                </div>
                {isOnline ? (
                  <span className="absolute -bottom-0.5 -right-0.5 z-10 h-3 w-3 rounded-full bg-sky-400 ring-2 ring-white" />
                ) : null}
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900">{fullName}</p>
                <p className="text-xs text-gray-500">{position}</p>
                <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                  <span className={`h-2 w-2 rounded-full ${dotColor}`} />
                  <span className={statusColor}>{statusText}</span>
                  {employee.email && (
                    <>
                      <span className="mx-1 text-gray-300">•</span>
                      <span className="text-gray-500">{employee.email}</span>
                    </>
                  )}
                </div>
              </div>
            </article>
          );
        })}

        <div ref={loaderRef} className="py-2">
          {loadingMore ? (
            <p className="text-center text-xs text-gray-500">Подгружаем сотрудников...</p>
          ) : !hasMore && employees.length > 0 ? (
            <p className="text-center text-xs text-gray-400">Все сотрудники загружены</p>
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}
