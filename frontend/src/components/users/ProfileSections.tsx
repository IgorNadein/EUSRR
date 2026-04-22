"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import {
  CalendarClock,
  Check,
  Clock3,
  Crown,
  Link2,
  Loader2,
  Pencil,
  Plus,
  Timer,
  X,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import type { EmployeeWorkSchedule } from "@/lib/api/attendance";
import type { EmployeeAction, EmployeeDepartment, Skill } from "@/types/api";
import { getEmployeeActionTone } from "@/lib/users/userDetailUtils";

export type ProfileContactRow = {
  key: string;
  label: string;
  value: string;
  icon: ReactNode;
  onClick?: () => void;
  copied?: boolean;
  action?: ReactNode;
};

export type ProfileInfoItem = {
  label: string;
  value: string;
};

const workScheduleDays = [
  { value: "Monday", label: "Пн" },
  { value: "Tuesday", label: "Вт" },
  { value: "Wednesday", label: "Ср" },
  { value: "Thursday", label: "Чт" },
  { value: "Friday", label: "Пт" },
  { value: "Saturday", label: "Сб" },
  { value: "Sunday", label: "Вс" },
];

const defaultWorkdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

function compactDays(days: string[]) {
  const labels = workScheduleDays
    .filter((day) => days.includes(day.value))
    .map((day) => day.label);
  return labels.length ? labels.join(", ") : "Не указаны";
}

function normalizeScheduleTime(value?: string) {
  if (!value) return "";
  return value.slice(0, 5);
}

function defaultSchedule(employeeId: number): EmployeeWorkSchedule {
  return {
    id: null,
    employee_id: employeeId,
    start_time: "08:00",
    end_time: "17:00",
    expected_hours: 9,
    workdays: [...defaultWorkdays],
    date_overrides: [],
    is_active: false,
    is_default: true,
    updated_by: null,
    created_at: null,
    updated_at: null,
  };
}

function SectionTitle({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <h2 className="app-card-caption">{title}</h2>
      {action}
    </div>
  );
}

export function ProfileHeroCard({
  caption,
  statusBadge,
  avatar,
  fullName,
  secondaryLine,
  roleText,
  departmentBadge,
  headerActions,
  actionRow,
  bottomPanel,
}: {
  caption: string;
  statusBadge?: ReactNode;
  avatar: ReactNode;
  fullName: string;
  secondaryLine?: string | null;
  roleText: string;
  departmentBadge?: ReactNode;
  headerActions?: ReactNode;
  actionRow?: ReactNode;
  bottomPanel?: ReactNode;
}) {
  return (
    <section className="app-surface rounded-2xl p-5 sm:p-6">
      <div className="mb-4 flex items-start justify-between gap-4">
        <p className="app-card-caption">{caption}</p>
        {statusBadge}
      </div>

      <div className="space-y-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
          {avatar}

          <div className="min-w-0 flex-1">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
              <div className="min-w-0 flex-1">
                <h1 className="app-text-wrap text-[2rem] font-semibold leading-tight text-[var(--foreground)]">
                  {fullName}
                </h1>
                {secondaryLine ? (
                  <p className="app-text-muted mt-1.5 text-sm">{secondaryLine}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="app-text-muted text-sm">{roleText}</span>
                  {departmentBadge}
                </div>
              </div>
              {headerActions ? <div className="flex shrink-0 items-center gap-2">{headerActions}</div> : null}
            </div>

            {actionRow ? <div className="mt-3 flex flex-wrap gap-2">{actionRow}</div> : null}
          </div>
        </div>

        {bottomPanel}
      </div>
    </section>
  );
}

export function ProfileContactsPanel({
  rows,
  emptyText = "Контакты не указаны",
}: {
  rows: ProfileContactRow[];
  emptyText?: string;
}) {
  return (
    <div className="app-surface-muted rounded-2xl p-4">
      {rows.length ? (
        rows.map((row, index) => (
          <div key={row.key}>
            {index > 0 ? <div className="mx-4 border-t border-[var(--border-subtle)]" /> : null}
            <div className="flex items-start gap-3 px-4 py-4">
              <span className="app-badge mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
                {row.icon}
              </span>
              {row.onClick ? (
                <button
                  type="button"
                  onClick={row.onClick}
                  className="min-w-0 flex-1 text-left"
                  title="Скопировать"
                >
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      {row.label}
                    </p>
                    {row.copied ? (
                      <span className="app-text-muted text-xs">Скопировано</span>
                    ) : null}
                  </div>
                  <p className="app-text-wrap app-text-muted mt-1 text-sm transition hover:text-[var(--accent-primary)]">
                    {row.value}
                  </p>
                </button>
              ) : (
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      {row.label}
                    </p>
                    {row.copied ? (
                      <span className="app-text-muted text-xs">Скопировано</span>
                    ) : null}
                  </div>
                  <p className="app-text-wrap app-text-muted mt-1 text-sm">
                    {row.value}
                  </p>
                </div>
              )}
              {row.action ? <div className="shrink-0">{row.action}</div> : null}
            </div>
          </div>
        ))
      ) : (
        <p className="app-text-muted px-4 py-2 text-sm">{emptyText}</p>
      )}
    </div>
  );
}

export function ProfileInfoCard({
  title = "Информация",
  items,
}: {
  title?: string;
  items: ProfileInfoItem[];
}) {
  return (
    <section className="app-surface rounded-2xl p-5">
      <SectionTitle title={title} />
      <div className="app-surface-muted overflow-hidden rounded-2xl">
        <div className="grid md:grid-cols-2">
          {items.map((item, index) => (
            <div
              key={item.label}
              className={[
                "px-4 py-3.5",
                index > 0 ? "border-t border-[var(--border-subtle)]" : "",
                index % 2 === 1 ? "md:border-l" : "",
                index === 1 ? "md:border-t-0" : "",
              ].join(" ").trim()}
            >
              <p className="text-sm font-semibold text-[var(--foreground)]">
                {item.label}
              </p>
              <p className="app-text-muted mt-1 text-sm">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function ProfileWorkScheduleCard({
  title = "График работы",
  employeeId,
  canEdit = false,
  currentAction,
}: {
  title?: string;
  employeeId: number;
  canEdit?: boolean;
  currentAction?: EmployeeAction | null;
}) {
  const [schedule, setSchedule] = useState<EmployeeWorkSchedule>(() =>
    defaultSchedule(employeeId),
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    start_time: "08:00",
    end_time: "17:00",
    expected_hours: "9",
    workdays: [...defaultWorkdays],
  });

  useEffect(() => {
    let mounted = true;

    async function loadSchedule() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getEmployeeWorkSchedule(employeeId);
        if (!mounted) return;
        setSchedule(data);
        setForm({
          start_time: normalizeScheduleTime(data.start_time) || "08:00",
          end_time: normalizeScheduleTime(data.end_time) || "17:00",
          expected_hours: String(data.expected_hours ?? 9),
          workdays: data.workdays?.length ? [...data.workdays] : [...defaultWorkdays],
        });
      } catch (loadError) {
        if (!mounted) return;
        setError(String((loadError as Error)?.message || "Не удалось загрузить график"));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadSchedule();

    return () => {
      mounted = false;
    };
  }, [employeeId]);

  const startTime = normalizeScheduleTime(schedule.start_time) || "08:00";
  const endTime = normalizeScheduleTime(schedule.end_time) || "17:00";
  const expectedHours = Number(schedule.expected_hours || 0) || 9;
  const workdays = schedule.workdays?.length ? schedule.workdays : defaultWorkdays;
  const weekendDays = workScheduleDays
    .map((day) => day.value)
    .filter((day) => !workdays.includes(day));
  const actionTone = currentAction
    ? getEmployeeActionTone(currentAction.action)
    : null;

  const toggleFormWorkday = (day: string) => {
    setForm((current) => ({
      ...current,
      workdays: current.workdays.includes(day)
        ? current.workdays.filter((item) => item !== day)
        : [...current.workdays, day],
    }));
  };

  const saveSchedule = async () => {
    if (saving) return;
    try {
      setSaving(true);
      setError(null);
      const updated = await apiClient.updateEmployeeWorkSchedule(employeeId, {
        start_time: form.start_time,
        end_time: form.end_time,
        expected_hours: Number(form.expected_hours) || 0,
        workdays: form.workdays,
        date_overrides: schedule.date_overrides || [],
        is_active: true,
      });
      setSchedule(updated);
      setEditing(false);
    } catch (saveError) {
      setError(String((saveError as Error)?.message || "Не удалось сохранить график"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="app-surface rounded-2xl p-5">
      <SectionTitle
        title={title}
        action={(
          <div className="flex flex-wrap items-center justify-end gap-2">
            {schedule.is_default ? (
              <span className="app-status-pill app-feedback-warning">
                По умолчанию
              </span>
            ) : currentAction ? (
              <span className={`app-status-pill ${actionTone?.badgeClass || ""}`}>
                {currentAction.action_display || currentAction.action}
              </span>
            ) : (
              <span className="app-status-pill app-feedback-success">Активен</span>
            )}
            {canEdit ? (
              <button
                type="button"
                onClick={() => setEditing((current) => !current)}
                className="app-action-ghost flex h-8 w-8 items-center justify-center rounded-md"
                title="Редактировать график"
                aria-label="Редактировать график"
              >
                {editing ? <X size={15} /> : <Pencil size={15} />}
              </button>
            ) : null}
          </div>
        )}
      />

      <div className="app-surface-muted rounded-2xl p-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Loader2 size={16} className="animate-spin" />
            Загружаем график...
          </div>
        ) : null}

        {!loading && editing ? (
          <div className="mb-4 space-y-3 rounded-xl border border-[var(--border-subtle)] p-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <label className="block">
                <span className="app-card-caption mb-1 block">Начало</span>
                <input
                  type="time"
                  value={form.start_time}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, start_time: event.target.value }))
                  }
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-1 block">Конец</span>
                <input
                  type="time"
                  value={form.end_time}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, end_time: event.target.value }))
                  }
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="app-card-caption mb-1 block">Часов</span>
                <input
                  type="number"
                  min="1"
                  max="24"
                  step="0.25"
                  value={form.expected_hours}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      expected_hours: event.target.value,
                    }))
                  }
                  className="app-input w-full rounded-lg px-3 py-2 text-sm"
                />
              </label>
            </div>

            <div className="flex flex-wrap gap-2">
              {workScheduleDays.map((day) => {
                const active = form.workdays.includes(day.value);
                return (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => toggleFormWorkday(day.value)}
                    className={active
                      ? "app-action-primary rounded-lg px-3 py-2 text-xs font-medium"
                      : "app-action-secondary rounded-lg px-3 py-2 text-xs font-medium"
                    }
                  >
                    {day.label}
                  </button>
                );
              })}
            </div>

            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="app-action-secondary rounded-xl px-4 py-2 text-sm font-medium"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={() => void saveSchedule()}
                disabled={saving}
                className="app-action-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-50"
              >
                {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
                Сохранить
              </button>
            </div>
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex items-start gap-3">
            <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
              <Clock3 size={18} />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--foreground)]">
                {startTime} — {endTime}
              </p>
              <p className="app-text-muted mt-1 text-sm">Рабочее время</p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <span className="app-badge flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
              <Timer size={18} />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[var(--foreground)]">
                {expectedHours.toLocaleString("ru-RU")} ч.
              </p>
              <p className="app-text-muted mt-1 text-sm">Норма в день</p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {workScheduleDays.map((day) => {
            const active = workdays.includes(day.value);
            return (
              <span
                key={day.value}
                className={[
                  "inline-flex h-9 w-9 items-center justify-center rounded-xl border text-xs font-semibold",
                  active
                    ? "border-[color:color-mix(in_srgb,var(--accent-primary)_45%,var(--border-subtle))] bg-[color:color-mix(in_srgb,var(--accent-primary)_16%,transparent)] text-[var(--accent-primary)]"
                    : "border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-[var(--muted-foreground)]",
                ].join(" ")}
              >
                {day.label}
              </span>
            );
          })}
        </div>

        <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-xl border border-[var(--border-subtle)] px-3 py-2">
            <p className="app-card-caption mb-1">Рабочие дни</p>
            <p className="app-text-wrap text-[var(--foreground)]">
              {compactDays(workdays)}
            </p>
          </div>
          <div className="rounded-xl border border-[var(--border-subtle)] px-3 py-2">
            <p className="app-card-caption mb-1">Выходные</p>
            <p className="app-text-wrap text-[var(--foreground)]">
              {compactDays(weekendDays)}
            </p>
          </div>
        </div>

        {currentAction ? (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-[var(--border-subtle)] px-3 py-2 text-sm">
            <CalendarClock size={16} className="mt-0.5 shrink-0 text-[var(--muted-foreground)]" />
            <p className="app-text-muted app-text-wrap">
              Кадровое состояние с {currentAction.date_display || currentAction.date}
            </p>
          </div>
        ) : null}

        {error ? (
          <p className="mt-3 text-sm text-red-400">{error}</p>
        ) : null}
      </div>
    </section>
  );
}

export function ProfileSkillsCard({
  title = "Навыки",
  inputValue,
  onInputChange,
  onSubmit,
  submitDisabled,
  inputDisabled,
  availableSkills,
  skills,
  error,
  loading,
  onRemoveSkill,
  removeDisabled,
  emptyText = "Навыки не указаны",
}: {
  title?: string;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSubmit: () => void;
  submitDisabled: boolean;
  inputDisabled?: boolean;
  availableSkills: Skill[];
  skills: Skill[];
  error?: string | null;
  loading?: boolean;
  onRemoveSkill?: (skillId: number) => void;
  removeDisabled?: boolean;
  emptyText?: string;
}) {
  const listId = `${title.toLowerCase().replace(/\s+/g, "-")}-skills-list`;

  return (
    <section className="app-surface rounded-2xl p-5">
      <SectionTitle title={title} />
      <div className="app-surface-muted rounded-2xl p-3.5">
        <div className="flex flex-col gap-2.5 md:flex-row">
          <div className="min-w-0 flex-1">
            <input
              list={listId}
              value={inputValue}
              onChange={(event) => onInputChange(event.target.value)}
              placeholder="Добавить навык"
              className="app-input w-full rounded-xl px-4 py-2.5 text-sm"
              disabled={inputDisabled}
            />
            <datalist id={listId}>
              {availableSkills.map((skill) => (
                <option key={skill.id} value={skill.name} />
              ))}
            </datalist>
          </div>
          <button
            type="button"
            onClick={onSubmit}
            disabled={submitDisabled}
            className="app-action-primary inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium disabled:opacity-50"
          >
            <Plus size={16} />
            Добавить
          </button>
        </div>

        {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}

        <div className="mt-3">
          {skills.length ? (
            <div className="flex flex-wrap gap-2">
              {skills.map((skill) =>
                onRemoveSkill ? (
                  <button
                    key={skill.id}
                    type="button"
                    onClick={() => onRemoveSkill(skill.id)}
                    disabled={removeDisabled}
                    className="app-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] disabled:opacity-50"
                    title="Удалить навык"
                  >
                    <span>{skill.name}</span>
                    <X size={14} />
                  </button>
                ) : (
                  <span
                    key={skill.id}
                    className="app-pill inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium"
                  >
                    {skill.name}
                  </span>
                ),
              )}
            </div>
          ) : (
            <p className="app-text-muted text-sm">{emptyText}</p>
          )}
        </div>

        {loading ? (
          <p className="app-text-muted mt-2.5 text-sm">Загружаем навыки...</p>
        ) : null}
      </div>
    </section>
  );
}

export function ProfileDepartmentBadge({
  label,
  href,
}: {
  label: string;
  href?: string;
}) {
  if (href) {
    return (
      <Link
        href={href}
        className="app-pill inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
      >
        {label}
      </Link>
    );
  }

  return (
    <span className="app-pill inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
      {label}
    </span>
  );
}

export function ProfileDepartmentsCard({
  title = "Отделы",
  departments,
}: {
  title?: string;
  departments: EmployeeDepartment[];
}) {
  if (!departments.length) {
    return null;
  }

  return (
    <section className="app-surface rounded-2xl p-5">
      <SectionTitle title={title} />
      <div className="app-surface-muted rounded-2xl p-4">
        <div className="flex flex-wrap gap-2">
          {departments.map((department) => (
            <Link
              key={department.id}
              href={`/departments/${department.id}`}
              className="app-badge inline-flex max-w-full items-center gap-2 rounded-full px-2 py-1.5 text-[var(--foreground)] transition hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
            >
              <span className="truncate px-1 text-sm font-medium">
                {department.name}
              </span>
              {department.role_name ? (
                <span className="app-surface inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-xs font-medium text-[var(--muted-foreground)]">
                  <span className="truncate">{department.role_name}</span>
                </span>
              ) : null}
              {department.is_head ? (
                <span
                  className="inline-flex items-center justify-center rounded-full border border-[color:color-mix(in_srgb,#f59e0b_42%,var(--border-subtle))] bg-[color:color-mix(in_srgb,#f59e0b_14%,transparent)] px-2.5 py-1 text-[#f59e0b]"
                  title="Руководитель отдела"
                >
                  <Crown size={12} />
                </span>
              ) : null}
              {department.via_assignment ? (
                <span
                  className="app-surface inline-flex items-center justify-center rounded-full px-2.5 py-1"
                  title="Роль в отделе без прямого членства"
                >
                  <Link2 size={12} />
                </span>
              ) : null}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
