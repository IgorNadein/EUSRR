"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Plus, X } from "lucide-react";
import type { Skill } from "@/types/api";

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
    <section className="app-surface rounded-[28px] p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <p className="app-card-caption">{caption}</p>
        {statusBadge}
      </div>

      <div className="space-y-4">
        <div className="flex items-start gap-4">
          {avatar}

          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-3">
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
    <section className="app-surface rounded-[24px] p-5">
      <SectionTitle title={title} />
      <div className="app-surface-muted overflow-hidden rounded-2xl">
        <div className="grid md:grid-cols-2">
          {items.map((item, index) => (
            <div
              key={item.label}
              className={[
                "px-4 py-3.5",
                index % 2 === 1 ? "border-t border-[var(--border-subtle)] md:border-l md:border-t-0" : "",
                index >= 2 ? "border-t border-[var(--border-subtle)]" : "",
                index >= 2 && index % 2 === 1 ? "md:border-l" : "",
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
      <section className="app-surface rounded-[24px] p-5">
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
