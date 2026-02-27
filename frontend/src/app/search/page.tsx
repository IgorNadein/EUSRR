"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../components/AppShell";
import { apiClient } from "@/lib/api";
import type { Chat, Department, Document, Post, Request, User } from "@/types/api";
import { Search } from "lucide-react";

type SearchState = {
  employees: User[];
  departments: Department[];
  documents: Document[];
  requests: Request[];
  chats: Chat[];
  posts: Post[];
};

const emptyState: SearchState = {
  employees: [],
  departments: [],
  documents: [],
  requests: [],
  chats: [],
  posts: [],
};

function contains(value: string | undefined, query: string): boolean {
  return (value || "").toLowerCase().includes(query);
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const queryRaw = searchParams.get("q") || "";
  const query = queryRaw.trim().toLowerCase();

  const [results, setResults] = useState<SearchState>(emptyState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      setResults(emptyState);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function runSearch() {
      try {
        setLoading(true);
        setError(null);

        const [employees, departments, documents, requests, chats, posts] = await Promise.all([
          apiClient.getEmployees({ search: queryRaw, limit: 20 }),
          apiClient.getDepartments({ search: queryRaw, limit: 20 }),
          apiClient.getDocuments({ search: queryRaw, limit: 20 }),
          apiClient.getRequests({ search: queryRaw, limit: 20 }),
          apiClient.getChats({ search: queryRaw, limit: 20 }),
          apiClient.getPosts({ search: queryRaw, limit: 20 }),
        ]);

        if (cancelled) return;

        const filtered: SearchState = {
          employees: (employees.results || []).filter((u) =>
            contains(`${u.last_name} ${u.first_name} ${u.patronymic || ""}`, query) ||
            contains(u.email, query)
          ),
          departments: (departments.results || []).filter((d) =>
            contains(d.name, query) || contains(d.description, query)
          ),
          documents: (documents.results || []).filter((d) =>
            contains(d.title, query) || contains(d.description, query) || contains(d.document_type, query)
          ),
          requests: (requests.results || []).filter((r) =>
            contains(r.title, query) || contains(r.description, query) || contains(r.request_type, query)
          ),
          chats: (chats.results || []).filter((c) => contains(c.name, query) || contains(c.last_message?.content, query)),
          posts: (posts.results || []).filter((p) => contains(p.content, query)),
        };

        setResults(filtered);
      } catch (err) {
        if (!cancelled) {
          console.error("Ошибка поиска:", err);
          setError("Не удалось выполнить поиск");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    runSearch();

    return () => {
      cancelled = true;
    };
  }, [query, queryRaw]);

  const total = useMemo(
    () =>
      results.employees.length +
      results.departments.length +
      results.documents.length +
      results.requests.length +
      results.chats.length +
      results.posts.length,
    [results]
  );

  return (
    <AppShell>
      <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
        <div className="mb-4 flex items-center gap-2">
          <Search size={16} className="text-gray-400" />
          <p className="text-sm text-gray-600">
            {query ? `Результаты по запросу: ${queryRaw}` : "Введите запрос в поиске сверху"}
          </p>
        </div>

        {loading ? (
          <div className="rounded-xl bg-gray-50 p-6 text-center text-sm text-gray-500">Идёт поиск...</div>
        ) : error ? (
          <div className="rounded-xl bg-red-50 p-6 text-center text-sm text-red-800">{error}</div>
        ) : !query ? (
          <div className="rounded-xl bg-gray-50 p-6 text-center text-sm text-gray-500">Начните вводить запрос в строке поиска</div>
        ) : total === 0 ? (
          <div className="rounded-xl bg-gray-50 p-6 text-center text-sm text-gray-500">Ничего не найдено</div>
        ) : (
          <div className="space-y-4">
            {results.employees.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Сотрудники</p>
                <div className="space-y-2">
                  {results.employees.map((u) => (
                    <Link key={u.id} href="/employees" className="block rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50">
                      {`${u.last_name} ${u.first_name}`.trim()} {u.email ? `• ${u.email}` : ""}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}

            {results.departments.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Отделы</p>
                <div className="space-y-2">
                  {results.departments.map((d) => (
                    <Link key={d.id} href="/departments" className="block rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50">
                      {d.name}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}

            {results.requests.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Заявления</p>
                <div className="space-y-2">
                  {results.requests.map((r) => (
                    <Link key={r.id} href="/requests" className="block rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50">
                      {r.title}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}

            {results.documents.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Документы</p>
                <div className="space-y-2">
                  {results.documents.map((d) => (
                    <Link key={d.id} href="/documents" className="block rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50">
                      {d.title}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}

            {results.chats.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Чаты</p>
                <div className="space-y-2">
                  {results.chats.map((c) => (
                    <Link key={c.id} href={`/messages/${c.id}`} className="block rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50">
                      {c.name || `Чат #${c.id}`}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}

            {results.posts.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Посты</p>
                <div className="space-y-2">
                  {results.posts.map((p) => (
                    <Link key={p.id} href="/" className="block rounded-lg border border-gray-100 px-3 py-2 text-sm hover:bg-gray-50">
                      {p.content?.slice(0, 120) ?? "Без текста"}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </AppShell>
  );
}
