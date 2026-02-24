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

  // Приоритет same-origin: для /media/... в dev/proxy это самый надёжный путь.
  if (raw.startsWith("/")) return raw;

  if (BACKEND_URL) {
    const base = BACKEND_URL.replace(/\/$/, "");
    return `${base}/${raw.replace(/^\/+/, "")}`;
  }

  return `/${raw.replace(/^\/+/, "")}`;
}

export default function UserDetailPage() {
  const params = useParams<{ id: string }>();
  const userId = Number(params?.id);

  const [person, setPerson] = useState<User | null>(null);
  const [avatarFailed, setAvatarFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadUser() {
      if (!userId || Number.isNaN(userId)) {
        setError("Некорректный идентификатор пользователя");
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getEmployee(userId);
        setPerson(data);
      } catch (e: any) {
        setError(String(e?.message || "Не удалось загрузить пользователя"));
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, [userId]);

  useEffect(() => {
    setAvatarFailed(false);
  }, [person?.avatar, person?.id]);

  const fullName = useMemo(() => {
    if (!person) return "";
    return `${person.last_name || ""} ${person.first_name || ""} ${person.patronymic || ""}`.trim() || "Пользователь";
  }, [person]);

  const avatarUrl = resolveMediaUrl(person?.avatar);
  const initials = `${person?.last_name?.[0] || ""}${person?.first_name?.[0] || ""}` || "П";

  return (
    <AppShell>
      <div className="space-y-4">
        <Link href="/users" className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
          ← К списку пользователей
        </Link>

        {loading ? (
          <div className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-gray-100">
            <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
            <p className="text-sm text-gray-500">Загрузка пользователя...</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-red-50 p-6 text-center">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        ) : person ? (
          <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-lg font-semibold text-white">
                {avatarUrl && !avatarFailed ? (
                  <Image
                    src={avatarUrl}
                    alt={fullName}
                    width={64}
                    height={64}
                    className="h-full w-full object-cover"
                    unoptimized
                    onError={() => setAvatarFailed(true)}
                  />
                ) : (
                  <span>{initials}</span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <h1 className="truncate text-xl font-semibold text-gray-900">{fullName}</h1>
                <p className="mt-1 text-sm text-gray-600">Должность: {person.position?.name || "—"}</p>
                <p className="mt-1 text-sm text-gray-600">Email: {person.email || "—"}</p>
                <p className="mt-1 text-sm text-gray-600">Телефон: {person.phone_number || "—"}</p>
                <p className="mt-1 text-sm text-gray-600">Telegram: {person.telegram || "—"}</p>
                <p className="mt-1 text-sm text-gray-600">WhatsApp: {person.whatsapp || "—"}</p>
                {person.wechat ? <p className="mt-1 text-sm text-gray-600">WeChat: {person.wechat}</p> : null}
              </div>
            </div>

            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Отделы</p>
              {(person.departments || []).length === 0 ? (
                <p className="text-sm text-gray-500">Не указаны</p>
              ) : (
                <div className="space-y-2">
                  {(person.departments || []).map((d) => (
                    <Link key={d.id} href={`/departments/${d.id}`} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-800 hover:bg-gray-100">
                      <span>{d.name}</span>
                      {d.is_head ? <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-700">Руководитель</span> : null}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
