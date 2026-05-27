"use client";

import { AppShell } from "../../components/AppShell";
import { Modal } from "@/components/ui/Modal";
import { useUser } from "@/contexts/UserContext";
import { apiClient } from "@/lib/api";
import { loadAllPages } from "@/lib/shared";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Department } from "@/types/api";
import { Building2, Plus, Search, Users } from "lucide-react";

const scopeTabs = [
  { value: "all", label: "Все" },
  { value: "mine", label: "Мои" },
] as const;

export default function DepartmentsPage() {
  const { user } = useUser();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<"all" | "mine">("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ name: "", description: "" });

  const canCreateDepartment = Boolean(
    user?.auth?.is_staff || user?.auth?.is_superuser,
  );
  const myDepartmentIds = useMemo(
    () => new Set((user?.departments || []).map((department) => department.id)),
    [user?.departments],
  );

  useEffect(() => {
    async function loadDepartments() {
      try {
        setLoading(true);
        setError(null);
        const allDepartments = await loadAllPages<Department>((params) =>
          apiClient.getDepartments(params),
        );
        setDepartments(allDepartments);
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
    const visibleDepartments = scope === "mine"
      ? departments.filter((department) => myDepartmentIds.has(department.id))
      : departments;
    const sorted = [...visibleDepartments].sort((a, b) => a.name.localeCompare(b.name, "ru"));
    if (!q) return sorted;

    return sorted.filter((dep) => {
      const name = dep.name.toLowerCase();
      const desc = (dep.description || "").toLowerCase();
      const head = dep.head ? `${dep.head.last_name} ${dep.head.first_name}`.toLowerCase() : "";
      return name.includes(q) || desc.includes(q) || head.includes(q);
    });
  }, [departments, myDepartmentIds, scope, search]);

  const scopeCounts = useMemo(
    () => ({
      all: departments.length,
      mine: departments.filter((department) => myDepartmentIds.has(department.id)).length,
    }),
    [departments, myDepartmentIds],
  );

  async function handleCreateDepartment() {
    const name = draft.name.trim();
    const description = draft.description.trim();

    if (!name) {
      setCreateError("Укажите название отдела");
      return;
    }

    try {
      setCreating(true);
      setCreateError(null);

      const created = await apiClient.createDepartment({
        name,
        description: description || undefined,
      }) as Department;

      setDepartments((current) => [...current, created]);
      setCreateOpen(false);
      setDraft({ name: "", description: "" });
    } catch (err) {
      console.error("Ошибка создания отдела:", err);
      setCreateError("Не удалось создать отдел");
    } finally {
      setCreating(false);
    }
  }

  function openCreateDepartment() {
    setCreateError(null);
    setDraft({ name: "", description: "" });
    setCreateOpen(true);
  }

  function closeCreateDepartment() {
    if (creating) return;
    setCreateOpen(false);
    setCreateError(null);
  }

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
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="app-text-muted text-sm font-semibold uppercase tracking-wide">Отделы</p>
            {canCreateDepartment ? (
              <button
                type="button"
                onClick={openCreateDepartment}
                className="app-action-primary inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium"
              >
                <Plus size={14} /> Создать отдел
              </button>
            ) : null}
          </div>

          <div className="relative mb-4">
            <Search size={16} className="app-text-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по отделам"
              className="app-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            />
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {scopeTabs.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => setScope(tab.value)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  scope === tab.value ? "app-pill-active" : "app-pill"
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`app-badge px-1.5 py-0.5 text-[10px] font-bold ${
                    scope === tab.value ? "app-pill-count-active" : "app-pill-count"
                  }`}
                >
                  {scopeCounts[tab.value]}
                </span>
              </button>
            ))}
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

      <Modal
        isOpen={createOpen}
        onClose={closeCreateDepartment}
        title="Создать отдел"
        size="md"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={closeCreateDepartment}
              className="app-action-secondary rounded-lg px-4 py-2 text-sm"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void handleCreateDepartment()}
              disabled={creating}
              className="app-action-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50"
            >
              {creating ? "Создание..." : "Создать"}
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {createError ? (
            <p className="app-feedback-danger rounded-lg px-3 py-2 text-sm">{createError}</p>
          ) : null}

          <section className="app-surface-muted rounded-xl p-4">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Название отдела *
            </label>
            <input
              value={draft.name}
              onChange={(event) =>
                setDraft((current) => ({ ...current, name: event.target.value }))
              }
              className="app-input w-full rounded-lg px-3 py-2 text-sm"
              placeholder="Например, Отдел закупок"
              disabled={creating}
            />
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Описание
            </label>
            <textarea
              value={draft.description}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
              className="app-input min-h-28 w-full rounded-lg px-3 py-2 text-sm"
              placeholder="Кратко опишите назначение отдела"
              disabled={creating}
            />
          </section>
        </div>
      </Modal>
    </AppShell>
  );
}
