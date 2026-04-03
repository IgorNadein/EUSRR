"use client";

import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { useUser } from "@/contexts/UserContext";
import type { User } from "@/types/api";

export default function EmployeesPage() {
  const router = useRouter();
  const { user: currentUser } = useUser();
  const [employees, setEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [creatingChatFor, setCreatingChatFor] = useState<number | null>(null);
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

      const response = await apiClient.getEmployees({ 
        page: pageToLoad, 
        limit: 20,
        is_active: true
      });
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

  // Создание чата с сотрудником
  const handleStartChat = async (employee: User, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!currentUser || creatingChatFor === employee.id) return;
    if (currentUser.id === employee.id) return; // Не создаем чат с собой
    
    setCreatingChatFor(employee.id);
    try {
      // Ищем существующий приватный чат с этим пользователем
      const allChats = await apiClient.getAllChats();
      
      const existingChat = allChats.find((chat: any) => {
        if (chat.type !== 'private') return false;
        
        const memberIds: number[] = chat.member_ids || [];
        return memberIds.length === 2 &&
               memberIds.includes(currentUser.id) &&
               memberIds.includes(employee.id);
      });
      
      if (existingChat) {
        router.push(`/messages/${existingChat.id}`);
      } else {
        const chat = await apiClient.createChat({
          type: 'private',
          name: 'Диалог',
          participants: [employee.id]
        });
        router.push(`/messages/${chat.id}`);
      }
    } catch (err: any) {
      console.error("Ошибка создания чата:", err);
      alert("Не удалось открыть чат");
    } finally {
      setCreatingChatFor(null);
    }
  };

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
          const isCurrentUser = currentUser?.id === employee.id;

          return (
            <div key={employee.id} className="flex items-center gap-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
              <Link href={`/users/${employee.id}`} className="flex flex-1 items-center gap-4 transition hover:opacity-80">
                <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
                  {employee.avatar ? (
                    <img src={employee.avatar} alt={fullName} className="h-full w-full object-cover" />
                  ) : (
                    initials
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-gray-900">{fullName}</p>
                  <p className="text-xs text-gray-500">{position}</p>
                  {employee.email && (
                    <p className="mt-1 text-xs text-gray-500">{employee.email}</p>
                  )}
                </div>
              </Link>
              {!isCurrentUser && (
                <button
                  onClick={(e) => handleStartChat(employee, e)}
                  disabled={creatingChatFor === employee.id}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-100 text-sky-600 transition hover:bg-sky-200 disabled:opacity-50"
                  title="Написать сообщение"
                >
                  {creatingChatFor === employee.id ? (
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-sky-600 border-t-transparent" />
                  ) : (
                    <MessageCircle size={18} />
                  )}
                </button>
              )}
            </div>
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
